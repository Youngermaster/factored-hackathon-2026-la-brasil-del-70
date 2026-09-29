"""The steps before any workflow handler: the session gate, language, untrusted-content checks, and signals.

Each function returns a ``Step`` that ends the turn, or ``None`` to continue.
"""

from datetime import UTC, datetime, time, timedelta

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.decide import evaluate
from bank_agent.application.engine.definition import AUTH_REQUIRED, StateKind
from bank_agent.application.engine.language import resolve_language
from bank_agent.application.engine.llm import DETECT_SIGNALS, structured
from bank_agent.application.engine.reply import Reply
from bank_agent.application.engine.security import INJECTION_DETECTOR, detect_injection, referenced_ids
from bank_agent.application.engine.shared import escalate_decision, refuse
from bank_agent.application.engine.signals import SIGNAL_DETECTOR, detect_signals, plain_answer
from bank_agent.application.engine.states import auth_required_reply
from bank_agent.domain.actions import ToolName
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.decision import DecisionKind
from bank_agent.domain.identifiers import ApplicationId, CaseId, ProductId, SourceRef, SourceTable, TransactionId
from bank_agent.domain.llm_outputs import EscalationSignals as ModelSignals
from bank_agent.domain.trust import TrustEvent, TrustEventKind
from bank_agent.domain.workflow import Outcome

REFERENCE_CHECKS = frozenset(
    {
        ToolName.GET_TRANSACTION,
        ToolName.GET_PRODUCT_STATUS,
        ToolName.GET_CASE_STATUS,
        ToolName.GET_CREDIT_APPLICATION_STATUS,
    }
)


async def add_trust_event(
    ctx: TurnContext, kind: TrustEventKind, detector: str, detail: str, evidence: SourceRef | None = None
) -> None:
    """Append risk evidence to the session lineage (outside the turn's unit of work, by design)."""
    last = ctx.trust.events[-1].occurred_at if ctx.trust.events else ctx.now
    event = TrustEvent(
        kind=kind,
        occurred_at=max(ctx.now, last),
        turn_id=ctx.turn_id,
        detector=detector,
        evidence=evidence,
        detail_code=detail,
    )
    ctx.trust = await ctx.services.session_store.append_trust_event(ctx.conversation.lineage_id, event)
    ctx.recorder.trust_events.append(kind)


def pause(ctx: TurnContext) -> Step:
    """The session expired or was revoked: run nothing privileged, remember where to resume, ask to re-verify."""
    ctx.recorder.intervention("session_expired")
    spec = ctx.definition.spec(ctx.state)
    if spec.kind is StateKind.TERMINAL or ctx.state == AUTH_REQUIRED:
        return Step(ctx.state, auth_required_reply())
    resume = spec.resume_state or ctx.state
    ctx.engine = ctx.engine.evolve(resume_state=resume)
    return Step(AUTH_REQUIRED, auth_required_reply())


def resume_after_sign_in(ctx: TurnContext) -> None:
    """A turn from a new session lineage (the customer signed in again) mid-flow resumes like after a pause.

    The HTTP layer never passes an expired session to the engine, so ``pause`` does not run for it; instead the
    first turn of the new login goes through AUTH_REQUIRED to the last safe state (a write state's ``resume_state``),
    and the question there is asked again, so a confirmation is never carried across a sign-in. A step-up rotates
    the session but keeps the lineage, so a stepped-up turn executes directly.
    """
    previous, current = ctx.engine.lineage, ctx.session.lineage_id
    ctx.engine = ctx.engine.evolve(lineage=current)
    if previous is None or previous == current or ctx.at_router or ctx.state == AUTH_REQUIRED:
        return
    spec = ctx.definition.spec(ctx.state)
    if spec.kind in (StateKind.TERMINAL, StateKind.ACCEPTS_REQUEST):
        return
    ctx.definition.check_transition(ctx.state, AUTH_REQUIRED)
    ctx.recorder.intervention("signed_in_again")
    ctx.engine = ctx.engine.evolve(resume_state=spec.resume_state or ctx.state)
    ctx.state = AUTH_REQUIRED


def resolve_turn_language(ctx: TurnContext) -> Step | None:
    detection = ctx.services.language_detector.detect(ctx.text)
    ctx.detection = detection
    ctx.recorder.model(detection.detector)
    if ctx.settings.fixed_language is not None:
        ctx.language = ctx.settings.fixed_language
        return None
    resolution = resolve_language(
        detection,
        text=ctx.text,
        preference=ctx.conversation.language,
        session_preference=ctx.session.language_preference,
        pending_text=ctx.engine.pending_language_text,
    )
    if resolution.language is None:
        ctx.engine = ctx.engine.evolve(pending_language_text=resolution.text)
        reply = Reply(template="common.language_question", bilingual=True)
        return Step(ctx.state, reply, Outcome.CLARIFIED)
    ctx.language = resolution.language
    ctx.text = UntrustedText(resolution.text)
    ctx.engine = ctx.engine.evolve(pending_language_text=None)
    return None


async def _references(ctx: TurnContext) -> None:
    found = referenced_ids(ctx.text)
    if not found.any:
        return
    foreign: list[SourceRef] = []
    with ctx.tools.engine_check(REFERENCE_CHECKS):
        for txn_id in found.transactions:
            txn = await ctx.tools.get_transaction(TransactionId(txn_id))
            if txn is None:
                foreign.append(SourceRef.of(SourceTable.TRANSACTIONS, txn_id))
            else:
                ctx.referenced_transaction = txn.transaction_id
        for product_id in found.products:
            if await ctx.tools.get_product_status(ProductId(product_id)) is None:
                foreign.append(SourceRef.of(SourceTable.PRODUCTS, product_id))
        for case_id in found.cases:
            if await ctx.tools.get_case_status(CaseId(case_id)) is None:
                foreign.append(SourceRef.of(SourceTable.DISPUTE_CASES, case_id))
        for application_id in found.applications:
            if await ctx.tools.get_credit_application_status(ApplicationId(application_id)) is None:
                foreign.append(SourceRef.of(SourceTable.CREDIT_APPLICATIONS, application_id))
    foreign.extend(
        SourceRef.of(SourceTable.CUSTOMERS, value) for value in found.customers if value != ctx.customer.customer_id
    )
    if foreign:
        ctx.privacy = ctx.privacy.evolve(other_customer_reference=True)
        await add_trust_event(ctx, TrustEventKind.CROSS_CUSTOMER_PROBE, "reference:session_scope@1", "not_visible")


def answers_pending_question(ctx: TurnContext) -> bool:
    """The turn is a plain yes or no while a question is pending: a workflow state that awaits an answer (a
    confirmation, an offer) or the engine's own switch question."""
    if not plain_answer(ctx.text):
        return False
    if ctx.engine.pending_switch is not None:
        return True
    return not ctx.at_router and ctx.definition.spec(ctx.state).kind is StateKind.AWAITS_ANSWER


async def inspect(ctx: TurnContext) -> Step | None:
    """Injection heuristics, escalation and privacy signals, and record ids named in the text; then the kernel's
    common rules (refusal and escalation triggers) at the workflow's START binding. A plain yes or no to a pending
    question is resolved deterministically: the model's signals are not asked for (the keywords still run)."""
    if detect_injection(ctx.text):
        ctx.recorder.intervention("injection_detected")
        await add_trust_event(ctx, TrustEventKind.INJECTION_DETECTED, INJECTION_DETECTOR, "customer_text")
    model = None
    if not answers_pending_question(ctx):
        variables = {"customer_message": ctx.text, "dialect_hint": ctx.locale.value}
        model = await structured(ctx, DETECT_SIGNALS, variables, ModelSignals)
    signals = detect_signals(ctx.text, person_offered=ctx.engine.person_offered).merged(model)
    ctx.escalation = ctx.escalation.evolve(
        human_requested=signals.human_requested,
        legal_or_regulator_mention=signals.legal_or_regulator_mention,
        distress_signal=signals.distress,
        prior_complaints_in_lookback=ctx.prior_complaints,
    )
    if signals.third_party_admission:
        ctx.privacy = ctx.privacy.evolve(third_party_request=True)
        await add_trust_event(ctx, TrustEventKind.THIRD_PARTY_ADMISSION, SIGNAL_DETECTOR, "third_party")
    await _references(ctx)
    decision = evaluate(ctx, policy_state="START")
    if decision.kind is DecisionKind.REFUSE:
        return refuse(ctx, decision)
    if decision.kind is DecisionKind.ESCALATE:
        return escalate_decision(ctx, decision)
    return None


def complaint_lookback_start(ctx: TurnContext, lookback_days: int) -> datetime:
    start = ctx.services.policy.data_as_of - timedelta(days=lookback_days)
    return datetime.combine(start, time.min, UTC)
