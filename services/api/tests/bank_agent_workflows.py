"""Workflow test harness: the real policy pack and grounding, session-scoped tools over any backend, scripted
models, and helpers to drive a conversation turn by turn. Every value is a fixture."""

from __future__ import annotations

import itertools
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from functools import cache
from pathlib import Path

from bank_agent.adapters.llm.unconfigured import UnconfiguredLLMClient
from bank_agent.adapters.persistence.duckdb.gold import DATASET_CREDIT_BALANCE_CONVENTION
from bank_agent.application.engine.engine import TurnRequest, WorkflowEngine
from bank_agent.application.tools.banking import BankingTools, EngineOnlyTools, SessionToolset
from bank_agent.application.tools.base import ToolDependencies
from bank_agent.application.tools.context import SessionContext, ToolSettings
from bank_agent.application.tools.failure_injection import ToolFailureInjector
from bank_agent.bootstrap.policy import PolicyServices, build_policy
from bank_agent.bootstrap.retrieval import GroundingServices, build_grounding
from bank_agent.bootstrap.settings import PolicySettings, RetrievalSettings, WorkflowSettings
from bank_agent.bootstrap.workflows import build_workflows
from bank_agent.domain.access import AuthLevel, Role
from bank_agent.domain.actions import ToolFailureMode, ToolName
from bank_agent.domain.conversation import TurnResult
from bank_agent.domain.execution_record import ExecutionRecord
from bank_agent.domain.handoff import HandoffRecord
from bank_agent.domain.identifiers import ConversationId, CustomerId, HandoffId, LineageId, SessionId, TurnId
from bank_agent.domain.session import Session
from bank_agent.ports.llm import LLMClient
from bank_agent.ports.sessions import SessionStore
from bank_agent.ports.unit_of_work import UnitOfWorkFactory
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.ids import SequentialIdGenerator
from bank_agent_scenarios import NOW

POLICY_DIR = Path(__file__).resolve().parents[3] / "policies"


@cache
def shared_policy() -> tuple[PolicyServices, GroundingServices]:
    """The real pack and its BM25 grounding, loaded once per test process (both are immutable)."""
    policy = build_policy(PolicySettings(dir=POLICY_DIR), clock=FixedClock(NOW), ids=SequentialIdGenerator())
    return policy, build_grounding(RetrievalSettings(), policy.repository)


class FailingTools:
    """Session tools wrapped in the failure injector (tests and evaluations only)."""

    def __init__(self, tools: BankingTools, plan: Mapping[ToolName, ToolFailureMode]) -> None:
        self._tools, self._plan = tools, dict(plan)

    def for_session(self, context: SessionContext) -> SessionToolset:
        return ToolFailureInjector(
            self._tools.for_session(context), self._tools.for_session(context, commit=False), self._plan,
            environment="test",
        )  # fmt: skip

    def engine_only(self, context: SessionContext) -> EngineOnlyTools:
        return self._tools.engine_only(context)

    @property
    def dependencies(self) -> ToolDependencies:
        return self._tools.dependencies


@dataclass
class Harness:
    engine: WorkflowEngine
    baseline: WorkflowEngine
    uow_factory: UnitOfWorkFactory
    session_store: SessionStore
    clock: FixedClock
    turns: itertools.count[int] = field(default_factory=lambda: itertools.count(1))

    def session(self, customer_id: str, *, step_up: bool = False, session_id: str | None = None,
                lineage: str | None = None) -> Session:  # fmt: skip
        now = self.clock.now()
        current = Session(
            session_id=SessionId(session_id or f"ses-{customer_id.lower()}"),
            lineage_id=LineageId(lineage or f"lin-{customer_id.lower()}"),
            role=Role.CUSTOMER,
            customer_id=CustomerId(customer_id),
            auth_level=AuthLevel.OTP_VERIFIED,
            created_at=now,
            last_seen_at=now,
            idle_timeout=timedelta(minutes=15),
            absolute_expires_at=now + timedelta(minutes=60),
        )
        return current.with_step_up(now=now, until=now + timedelta(minutes=5)) if step_up else current

    async def say(self, text: str, session: Session, conversation: str | None = None, *, turn: str | None = None,
                  baseline: bool = False) -> TurnResult:  # fmt: skip
        turn_id = turn or f"9b2f0d1e-0000-4000-8000-{next(self.turns):012d}"
        request = TurnRequest(
            turn_id=TurnId(turn_id), text=text, session=session,
            conversation_id=ConversationId(conversation) if conversation else None,
        )  # fmt: skip
        return await (self.baseline if baseline else self.engine).process_turn(request)

    async def record(self, session: Session, turn_id: str) -> ExecutionRecord:
        async with self.uow_factory(session.access_context()) as uow:
            record = await uow.execution_records.get(TurnId(turn_id))
        assert record is not None
        return record

    async def handoff(self, session: Session, handoff_id: str) -> HandoffRecord:
        async with self.uow_factory(session.access_context()) as uow:
            stored = await uow.handoffs.get(HandoffId(handoff_id))
        assert stored is not None
        return stored


def build_harness(
    uow_factory: UnitOfWorkFactory,
    session_store: SessionStore,
    *,
    llm: LLMClient | None = None,
    failures: Mapping[ToolName, ToolFailureMode] | None = None,
    enabled: tuple[str, ...] = ("account_inquiry", "card_support", "dispute", "credit"),
    llm_understanding: bool = True,
    phrasing: bool = False,
    handoff_summary: bool = False,
) -> Harness:
    clock, ids = FixedClock(NOW), SequentialIdGenerator()
    policy, grounding = shared_policy()
    tools = BankingTools(
        ToolDependencies(
            uow_factory=uow_factory,
            catalog=policy.catalog,
            clock=clock,
            ids=ids,
            settings=ToolSettings(policy=policy.tool_policy, balance_convention=DATASET_CREDIT_BALANCE_CONVENTION),
        )
    )
    provider = FailingTools(tools, failures) if failures else tools
    services = build_workflows(
        WorkflowSettings(
            enabled=list(enabled),
            llm_understanding=llm_understanding,
            llm_phrasing=phrasing,
            llm_handoff_summary=handoff_summary,
        ),
        uow_factory=uow_factory,
        session_store=session_store,
        tools=provider,
        policy=policy,
        grounding=grounding,
        llm=llm or UnconfiguredLLMClient(),
        clock=clock,
        ids=ids,
        environment="test",
    )
    return Harness(services.engine(), services.engine("baseline_b0"), uow_factory, session_store, clock)
