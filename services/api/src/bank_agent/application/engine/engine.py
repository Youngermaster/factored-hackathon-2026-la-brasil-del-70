"""``WorkflowEngine.process_turn``: one customer message in, one ``TurnResult`` out, with one execution record.

Order: replay a known turn id; load the conversation, the customer, and the trust state; the session gate (an
expired session pauses the flow); the turn limit; language; untrusted-content checks and signals; routing and the
handler chain; rendering with grounding verification; then one unit of work stores the conversation, the turn, the
handoff (validated against its schema), and the execution record together.
"""

import time as monotonic_time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from pydantic import JsonValue

from bank_agent.application.engine.context import EngineServices, EngineSettings, Step, TurnContext
from bank_agent.application.engine.data import ENGINE_KEY, FLOW_KEY, dump, load_engine
from bank_agent.application.engine.flow import route_and_run
from bank_agent.application.engine.gate import inspect, pause, resolve_turn_language, resume_after_sign_in
from bank_agent.application.engine.handoff import validate_handoff
from bank_agent.application.engine.metrics import TurnMetrics
from bank_agent.application.engine.phrase import finish_reply
from bank_agent.application.engine.recorder import TurnRecorder
from bank_agent.application.engine.records import build_record
from bank_agent.application.engine.registry import WorkflowRegistry
from bank_agent.application.engine.render import Renderer
from bank_agent.application.engine.shared import escalate
from bank_agent.application.engine.summary import refine_summary
from bank_agent.application.engine.templates import PERSON_OFFER_TEMPLATES
from bank_agent.application.engine.tools import GuardedToolset
from bank_agent.application.tools.context import SessionContext
from bank_agent.domain.access import Channel
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.conversation import (
    MAX_CUSTOMER_MESSAGE_LENGTH,
    AssistantResponse,
    Conversation,
    ConversationStatus,
    Turn,
    TurnResult,
    WorkflowPosition,
)
from bank_agent.domain.customer import Customer
from bank_agent.domain.errors import ConversationNotFoundError, DuplicateEntityError, ToolArgumentError
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.execution_record import ExecutionRecord
from bank_agent.domain.identifiers import ConversationId, IdKind, TurnId
from bank_agent.domain.locale import Language
from bank_agent.domain.session import Session
from bank_agent.domain.workflow import WorkflowId, WorkflowRef
from bank_agent.ports.telemetry import AttributeValue, Span

ROUTER_REF = WorkflowRef(id="router", version=1)
ESCALATED_STATE = "ESCALATED"
LIMITED_SERVICE = "common.limited_service"
"""The prefix of every reply in template-only mode (L2): the customer learns the service is limited."""


@dataclass(frozen=True)
class TurnRequest:
    turn_id: TurnId
    text: str
    session: Session
    conversation_id: ConversationId | None = None
    channel: Channel = Channel.WEB_CHAT

    def __post_init__(self) -> None:
        if not self.text.strip() or len(self.text) > MAX_CUSTOMER_MESSAGE_LENGTH:
            raise ToolArgumentError(f"a message has 1 to {MAX_CUSTOMER_MESSAGE_LENGTH} characters")


@dataclass(frozen=True)
class Loaded:
    conversation: Conversation | None
    customer: Customer
    prior_complaints: int


class WorkflowEngine:
    def __init__(
        self,
        services: EngineServices,
        settings: EngineSettings,
        registry: WorkflowRegistry,
        renderer: Renderer,
        *,
        monotonic: Callable[[], float] = monotonic_time.perf_counter,
    ) -> None:
        self._services = services
        self._settings = settings
        self._registry = registry
        self._renderer = renderer
        self._monotonic = monotonic
        self._metrics = TurnMetrics(services.telemetry)

    @property
    def registry(self) -> WorkflowRegistry:
        return self._registry

    async def process_turn(self, request: TurnRequest) -> TurnResult:
        replayed = await self._replay(request)
        if replayed is not None:
            return replayed
        attributes: dict[str, AttributeValue] = {"bank.turn_id": request.turn_id, "bank.channel": request.channel}
        if request.conversation_id is not None:
            attributes["bank.conversation_id"] = request.conversation_id
        with self._services.telemetry.span("bank.turn", attributes) as span:
            return await self._process(request, span)

    async def _process(self, request: TurnRequest, span: Span) -> TurnResult:
        loaded = await self._load(request)
        now = self._services.clock.now()
        conversation = loaded.conversation or self.new_conversation(
            request.session, loaded.customer, now, request.channel
        )
        ctx = await self._context(request, conversation, loaded, now)
        step = await self._run(ctx)
        if step.next_state != ctx.state:
            ctx.definition.check_transition(ctx.state, step.next_state)
            ctx.state = step.next_state
        reply = step.reply
        if reply is None:
            raise RuntimeError("a turn must end with a reply")
        if ctx.resumed and reply.prefix is None:
            reply = replace(reply, prefix="common.resume")
        if ctx.degradation.template_only and reply.prefix is None:
            reply = replace(reply, prefix=LIMITED_SERVICE)
        response = await finish_reply(ctx, self._renderer, reply)
        await refine_summary(ctx)
        record = build_record(ctx, conversation, step, request.channel, now, trace_id=span.trace_id)
        try:
            await self._persist(ctx, conversation, loaded.conversation is None, request, response, record, now)
        except DuplicateEntityError:
            again = await self._replay(request)
            if again is None:
                raise
            return again
        span.set_attribute("bank.conversation_id", conversation.conversation_id)
        span.set_attribute("bank.workflow", record.workflow.id)
        span.set_attribute("bank.state", record.state_after)
        span.set_attribute("bank.outcome", record.outcome.value)
        reason = ctx.handoff.escalation_reason.code.value if ctx.handoff is not None else None
        self._metrics.observe(record, escalation_reason=reason)
        return TurnResult(
            turn_id=request.turn_id,
            conversation_id=conversation.conversation_id,
            state=ctx.state,
            outcome=record.outcome,
            response=response,
            workflow=record.workflow,
        )

    async def _replay(self, request: TurnRequest) -> TurnResult | None:
        async with self._services.uow_factory(request.session.access_context()) as uow:
            turn = await uow.conversations.get_turn(request.turn_id)
            record = await uow.execution_records.get(request.turn_id) if turn is not None else None
        if turn is None or turn.response is None or record is None:
            return None
        return TurnResult(
            turn_id=turn.turn_id,
            conversation_id=turn.conversation_id,
            state=record.state_after,
            outcome=record.outcome,
            response=turn.response,
            workflow=record.workflow,
            replayed=True,
        )

    async def _load(self, request: TurnRequest) -> Loaded:
        lookback = self._services.policy.pack.get_clause("ESC-ALL-1", Language.ES).metadata.params
        days = lookback.get("repeat_complaint_lookback_days")
        async with self._services.uow_factory(request.session.access_context()) as uow:
            customer = await uow.customers.get_current()
            conversation = None
            if request.conversation_id is not None:
                conversation = await uow.conversations.get(request.conversation_id)
                if conversation is None:
                    raise ConversationNotFoundError()
            start = self._services.policy.data_as_of - timedelta(days=days if isinstance(days, int) else 0)
            complaints = await uow.complaints.count_since(datetime.combine(start, time.min, UTC))
        return Loaded(conversation, customer, complaints)

    def new_conversation(
        self, session: Session, customer: Customer, now: datetime, channel: Channel = Channel.WEB_CHAT
    ) -> Conversation:
        """A new, empty conversation at the router's START, before any turn (phase 11 opens one explicitly)."""
        return Conversation(
            conversation_id=ConversationId(self._services.ids.new(IdKind.CONVERSATION)),
            customer_id=customer.customer_id,
            lineage_id=session.lineage_id,
            channel=channel,
            jurisdiction=customer.country,
            position=WorkflowPosition(workflow=ROUTER_REF, state="START"),
            created_at=now,
            updated_at=now,
        )

    async def _context(
        self, request: TurnRequest, conversation: Conversation, loaded: Loaded, now: datetime
    ) -> TurnContext:
        services, customer = self._services, loaded.customer
        session = request.session
        valid = not session.is_expired(now)
        session_context = SessionContext.of(session, services.clock) if valid else None
        tools_context = session_context or SessionContext(session=session, at=now)
        recorder = TurnRecorder(monotonic=self._monotonic)
        degradation = services.degradation.current()
        if degradation.degraded:
            recorder.intervention(f"degradation_{degradation.level.label.lower()}")
        retry_budget = services.policy.pack.get_clause("ESC-ALL-1", Language.ES).metadata.params["tool_retry_budget"]
        tools = GuardedToolset(
            services.tools.for_session(tools_context),
            recorder,
            retry_budget=retry_budget if isinstance(retry_budget, int) else 0,
            monotonic=self._monotonic,
            timeout_seconds=self._settings.tool_timeout_seconds,
            telemetry=services.telemetry,
        )
        position = conversation.position
        at_router = position.workflow == ROUTER_REF
        enabled = self._registry.ordered_enabled()
        definition = self._registry.definition(enabled[0] if at_router else _workflow_id(position.workflow))
        zone = ZoneInfo(customer.country.timezone_name)
        engine = load_engine(position.data)
        flow = position.data.get(FLOW_KEY)
        return TurnContext(
            services=services,
            settings=self._settings,
            turn_id=request.turn_id,
            text=UntrustedText(request.text),
            session=session,
            session_context=session_context,
            snapshot=session.snapshot(now),
            trust=await services.session_store.get_trust_state(conversation.lineage_id),
            customer=customer,
            conversation=conversation,
            language=conversation.language or session.language_preference or Language.ES,
            now=now,
            today=now.astimezone(zone).date(),
            zone=zone,
            definition=definition,
            state=position.state,
            engine=engine.evolve(sequence=engine.sequence + 1),
            recorder=recorder,
            tools=tools,
            flow=dict(flow) if isinstance(flow, dict) else {},
            clarifications_used=position.clarifications_used,
            turns_used=position.turns_used,
            enabled=enabled,
            at_router=at_router,
            prior_complaints=loaded.prior_complaints,
            degradation=degradation,
        )

    async def _run(self, ctx: TurnContext) -> Step:
        recorder = ctx.recorder
        with recorder.stage("gate"):
            if ctx.session_context is None:
                return pause(ctx)
            resume_after_sign_in(ctx)
            if ctx.engine.sequence > self._settings.max_turns and ctx.state != ESCALATED_STATE:
                return escalate(ctx, EscalationReasonCode.OTHER, "turn_limit_reached")
            asked = resolve_turn_language(ctx)
            if asked is not None:
                return asked
            if ctx.state != ESCALATED_STATE:
                stopped = await inspect(ctx)
                if stopped is not None:
                    return stopped
        with recorder.stage("workflow"):
            return await route_and_run(ctx, self._registry)

    async def _persist(
        self,
        ctx: TurnContext,
        conversation: Conversation,
        is_new: bool,
        request: TurnRequest,
        response: AssistantResponse,
        record: ExecutionRecord,
        now: datetime,
    ) -> None:
        offered = response.template_id in PERSON_OFFER_TEMPLATES and ctx.state != ESCALATED_STATE
        ctx.engine = ctx.engine.evolve(person_offered=offered)
        data: dict[str, JsonValue] = {ENGINE_KEY: dump(ctx.engine), FLOW_KEY: ctx.flow}
        position = WorkflowPosition(
            workflow=ROUTER_REF if ctx.at_router else ctx.definition.ref,
            state=ctx.state,
            clarifications_used=ctx.clarifications_used,
            turns_used=ctx.turns_used + 1,
            data=data,
        )
        status = ConversationStatus.ESCALATED if ctx.state == ESCALATED_STATE else ConversationStatus.ACTIVE
        updated = conversation.evolve(language=ctx.language, status=status, position=position, updated_at=now)
        turn = Turn(
            turn_id=request.turn_id,
            conversation_id=conversation.conversation_id,
            sequence=ctx.engine.sequence,
            received_at=now,
            customer_text=UntrustedText(request.text),
            language=ctx.language,
            response=response,
            completed_at=now,
        )
        async with self._services.uow_factory(ctx.session.access_context()) as uow:
            if is_new:
                await uow.conversations.add(updated)
            else:
                await uow.conversations.update(updated, expected_version=conversation.version)
            await uow.conversations.append_turn(turn)
            if ctx.handoff is not None:
                validate_handoff(ctx.handoff)
                await uow.handoffs.add(ctx.handoff)
            await uow.execution_records.append(record)
            await uow.commit()


def _workflow_id(ref: WorkflowRef) -> WorkflowId:
    return WorkflowId(ref.id)
