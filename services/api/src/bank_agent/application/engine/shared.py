"""Shared outcomes every workflow uses: escalate, abstain, refuse, out of scope, greeting, informational, step-up.

Each builds a ``Step`` from verified state and clause references; none writes customer text by hand.
"""

import asyncio

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.decide import current_intent, evaluate, explanation
from bank_agent.application.engine.definition import (
    ABSTAINED,
    AUTH_REQUIRED,
    ESCALATED,
    REFUSED,
    StateKind,
    UnsupportedRequest,
)
from bank_agent.application.engine.handoff import HandoffBuilder, HandoffPlan
from bank_agent.application.engine.reply import Param, Reply
from bank_agent.application.engine.templates.labels import CAPABILITIES, join
from bank_agent.application.grounding.retrieval import RetrievalDecision
from bank_agent.domain.cards import CardAction, CardRequest
from bank_agent.domain.conversation import EscalationNotice, NoticeCode
from bank_agent.domain.decision import ClauseRef, Decision, DecisionKind
from bank_agent.domain.eligibility import CreditReview
from bank_agent.domain.errors import ConfigurationError
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.execution_record import RetrievalDecisionCode, RetrievalRecord
from bank_agent.domain.identifiers import CaseId
from bank_agent.domain.locale import Language
from bank_agent.domain.trust import RiskTier
from bank_agent.domain.workflow import Intent, Outcome

BUILDER = HandoffBuilder()
REAUTH_NOTICES = (NoticeCode.SESSION_EXPIRED, NoticeCode.REAUTHENTICATION_REQUIRED)


def capabilities(ctx: TurnContext) -> str:
    language = Language.ES if ctx.language is Language.EN else ctx.language
    return join([CAPABILITIES[workflow][language] for workflow in ctx.enabled], language)


def clause_ref(ctx: TurnContext, clause_id: str) -> ClauseRef:
    return ctx.services.policy.pack.get_clause(clause_id, Language.ES).ref


def escalate(
    ctx: TurnContext,
    code: EscalationReasonCode,
    detail: str,
    *,
    decision: Decision | None = None,
    open_questions: tuple[str, ...] = (),
    card_request: CardRequest | None = None,
    case_ref: CaseId | None = None,
    intent: Intent | None = None,
    credit_review: CreditReview | None = None,
) -> Step:
    """Build and validate the handoff, and tell the customer when a person will contact them."""
    sla_clause = "CRD-ALL-3" if card_request is not None else f"ESC-{ctx.customer.country.value}-2"
    basis = (*(explanation(decision) if decision is not None else ()), clause_ref(ctx, sla_clause))
    chosen = intent or current_intent(ctx) or Intent.HUMAN_REQUEST
    questions = ctx.definition.open_questions
    if not open_questions and questions is not None and not ctx.at_router:
        open_questions = questions(ctx)
    plan = HandoffPlan(
        code=code,
        detail=detail,
        intent=chosen,
        open_questions=open_questions,
        policy_basis=basis,
        card_request=card_request,
        case_ref=case_ref,
        credit_review=credit_review,
    )
    handoff = BUILDER.build(ctx, plan)
    ctx.handoff = handoff
    due = handoff.sla_due.astimezone(ctx.zone).date()
    ctx.engine = ctx.engine.evolve(handoff_id=handoff.handoff_id, handoff_due=due)
    reply = Reply(
        template="common.escalated",
        params={"due": due},
        explain=basis,
        escalation=EscalationNotice(handoff_id=handoff.handoff_id, expected_response_by=handoff.sla_due),
    )
    return Step(ESCALATED, reply, Outcome.ESCALATED)


def abstain(
    ctx: TurnContext, template: str, explain: tuple[ClauseRef, ...], params: dict[str, Param] | None = None
) -> Step:
    reply = Reply(template=template, params=dict(params or {}), explain=explain)
    return Step(ABSTAINED, reply, Outcome.ABSTAINED)


def refuse(ctx: TurnContext, decision: Decision) -> Step:
    third_party = any(r.rule_id == "PRV.no_third_party_disclosure" and not r.passed for r in decision.rule_results)
    template = "common.refused_third_party" if third_party else "common.refused"
    reply = Reply(template=template, explain=explanation(decision), suffix=risk_notice(ctx))
    return Step(REFUSED, reply, Outcome.REFUSED)


def risk_notice(ctx: TurnContext) -> tuple[tuple[str, dict[str, Param]], ...]:
    """What the customer's next request will need after a refusal, from the session's risk tier: step-up while it is
    elevated (unless a step-up is already valid), a person once it is high (``ESC.risk_tier_high``). The reply says
    only that the request is the reason; it never names a detector or a trust event."""
    tier = ctx.trust.risk_tier
    if tier is RiskTier.HIGH:
        return (("common.refused_review_notice", {}),)
    if tier is RiskTier.ELEVATED and not ctx.snapshot.step_up_valid:
        return (("common.refused_step_up_notice", {}),)
    return ()


def off_topic(ctx: TurnContext) -> Step:
    """A message with no banking content at all (sports, weather, recipes): a ``SCOPE-ALL-1`` abstention that says
    what the assistant does, without the workflow question and without the offer of a person. The decision is
    evaluated with intent ``unsupported``, so the record names ``SCOPE.supported_intent`` as for out of scope."""
    evaluate(ctx, policy_state="START", intent=Intent.UNSUPPORTED)
    ctx.recorder.intervention("out_of_scope")
    ctx.recorder.intervention("off_topic")
    reply = Reply(
        template="common.off_topic",
        params={"capabilities": capabilities(ctx)},
        explain=(clause_ref(ctx, "SCOPE-ALL-1"),),
    )
    return Step(ABSTAINED, reply, Outcome.ABSTAINED)


def out_of_scope(ctx: TurnContext) -> Step:
    """A ``SCOPE`` clause-backed explanation of what the assistant can do, and an offer of a human."""
    decision = evaluate(ctx, policy_state="START", intent=Intent.UNSUPPORTED)
    ctx.recorder.intervention("out_of_scope")
    refs = (clause_ref(ctx, "SCOPE-ALL-1"), *explanation(decision))
    reply = Reply(template="common.out_of_scope", params={"capabilities": capabilities(ctx)}, explain=refs)
    return Step(ABSTAINED, reply, Outcome.ABSTAINED)


def abstain_unsupported(ctx: TurnContext, request: UnsupportedRequest) -> Step:
    """An in-domain request the workflow does not handle: the workflow's clauses, the ``SCOPE`` decision, and an
    offer of a human. The decision is evaluated with intent ``unsupported``, so it names ``SCOPE.supported_intent``."""
    decision = evaluate(ctx, policy_state="START", intent=Intent.UNSUPPORTED)
    ctx.recorder.intervention("out_of_scope")
    ctx.recorder.intervention(f"unsupported_{request.code}")
    refs = (*(clause_ref(ctx, clause_id) for clause_id in request.clauses), *explanation(decision))
    return Step(ABSTAINED, Reply(template=request.template, explain=refs), Outcome.ABSTAINED)


def greeting(ctx: TurnContext, *, clarify: bool = False) -> Step:
    template = "common.clarify_intent" if clarify else "common.greeting"
    reply = Reply(template=template, params={"capabilities": capabilities(ctx)})
    return Step(ctx.state, reply, Outcome.CLARIFIED if clarify else Outcome.IN_PROGRESS)


async def informational(ctx: TurnContext) -> Step:
    """Open retrieval (informational intent only): the cited clauses, or a clause-backed abstention.

    The search runs in a worker thread: a retriever may call remote services (the hosted embedding model and
    Qdrant, ADR 0047) with bounded timeouts, and those calls must not block the event loop.
    """
    evaluate(ctx, policy_state="START", intent=Intent.INFORMATIONAL)
    try:
        outcome = await asyncio.to_thread(
            ctx.services.informational.search,
            intent=Intent.INFORMATIONAL,
            text=ctx.text,
            customer=ctx.customer,
            language=ctx.language,
        )
    except ConfigurationError:
        ctx.recorder.intervention("retrieval_unavailable")
        return abstain(ctx, "common.informational_abstain", (clause_ref(ctx, "SCOPE-ALL-2"),))
    ctx.recorder.model(outcome.retriever)
    answered = outcome.decision is RetrievalDecision.ANSWER
    ctx.recorder.retrieval = RetrievalRecord(
        retriever=outcome.retriever,
        decision=RetrievalDecisionCode.ANSWER if answered else RetrievalDecisionCode.ABSTAIN,
        threshold=outcome.threshold,
        top_score=outcome.top_score,
        citations=outcome.citations,
    )
    if not answered:
        step = abstain(ctx, "common.informational_abstain", (clause_ref(ctx, "SCOPE-ALL-2"),))
        return Step(ctx.state, step.reply, Outcome.ABSTAINED)
    reply = Reply(template="common.informational_answer", explain=outcome.citations)
    return Step(ctx.state, reply, Outcome.RESOLVED)


def human_requested(ctx: TurnContext) -> Step:
    ctx.escalation = ctx.escalation.evolve(human_requested=True)
    decision = evaluate(ctx, policy_state="START")
    return escalate(ctx, EscalationReasonCode.HUMAN_REQUESTED, "customer asked for a person", decision=decision)


def step_up(ctx: TurnContext, state: str, *, because_of_risk: bool = False) -> Step:
    """Ask for step-up. When only the session's raised risk tier asks for it (a read that otherwise needs a verified
    session), the reply says the conversation's requests are the reason, without naming what was detected."""
    template = "common.step_up_required_risk" if because_of_risk else "common.step_up_required"
    if not ctx.at_router and ctx.definition.spec(state).kind is StateKind.ACCEPTS_REQUEST:
        ctx.engine = ctx.engine.evolve(step_up_state=state)
    return Step(state, Reply(template=template, step_up_required=True), Outcome.IN_PROGRESS)


def step_up_from_risk(ctx: TurnContext, decision: Decision) -> bool:
    """True when ``decision`` asks for step-up only because the risk tier is elevated: ``AUTH.required_level`` asks
    for it while no action needs step-up by itself (``AUTH.step_up_valid`` passed)."""
    if ctx.trust.risk_tier.rank < RiskTier.ELEVATED.rank:
        return False
    failing = {r.rule_id for r in decision.rule_results if not r.passed and r.effect is DecisionKind.REQUIRE_STEP_UP}
    return failing == {"AUTH.required_level"}


_CARD_REQUEST_ACTIONS = {
    EscalationReasonCode.CARD_UNBLOCK_REQUESTED: CardAction.UNBLOCK_REQUEST,
    EscalationReasonCode.CARD_REPLACEMENT_REQUESTED: CardAction.REPLACEMENT_REQUEST,
}
_CREDIT_REVIEW_CODES = frozenset(
    {EscalationReasonCode.CREDIT_REVIEW_REQUIRED, EscalationReasonCode.ELIGIBILITY_CONTESTED}
)


def escalation_code(
    decision: Decision,
    *,
    card_request: CardRequest | None = None,
    credit_review: CreditReview | None = None,
) -> EscalationReasonCode:
    """The handoff reason for an ``escalate`` decision, from its first decisive rule whose handoff section is present.

    A card request code needs a ``card_request`` for the same action, and a credit review code needs a
    ``credit_review``. When the escalation comes from elsewhere (an exhausted clarification budget or a tool failure
    while a replacement request is still open), the request rule stays decisive but its section is missing, so the
    next decisive rule gives the reason instead of producing a handoff that cannot validate.
    """
    codes = {
        "ESC.human_requested": EscalationReasonCode.HUMAN_REQUESTED,
        "ESC.legal_or_regulator_mention": EscalationReasonCode.LEGAL_OR_REGULATOR_MENTION,
        "ESC.distress_signal": EscalationReasonCode.DISTRESS_SIGNAL,
        "ESC.clarification_exhausted": EscalationReasonCode.CLARIFICATION_EXHAUSTED,
        "ESC.tool_failure_exhausted": EscalationReasonCode.TOOL_FAILURE,
        "ESC.verification_mismatch": EscalationReasonCode.VERIFICATION_MISMATCH,
        "ESC.repeat_complainer": EscalationReasonCode.REPEAT_COMPLAINER,
        "ESC.risk_tier_high": EscalationReasonCode.RISK_TIER_HIGH,
        "DSP.amount_within_auto_limit": EscalationReasonCode.AMOUNT_ABOVE_AUTO_LIMIT,
        "DSP.reason_supported": EscalationReasonCode.UNSUPPORTED_NEEDS_HUMAN,
        "DSP.case_within_sla": EscalationReasonCode.SLA_BREACHED,
        "CRD.unblock_requires_human": EscalationReasonCode.CARD_UNBLOCK_REQUESTED,
        "CRD.replacement_requires_human": EscalationReasonCode.CARD_REPLACEMENT_REQUESTED,
        "ESC.credit_review_required": EscalationReasonCode.CREDIT_REVIEW_REQUIRED,
        "ESC.eligibility_contested": EscalationReasonCode.ELIGIBILITY_CONTESTED,
    }
    for rule_id in decision.decisive_rule_ids:
        code = codes.get(rule_id)
        if code is None:
            continue
        action = _CARD_REQUEST_ACTIONS.get(code)
        if action is not None and (card_request is None or card_request.action is not action):
            continue
        if code in _CREDIT_REVIEW_CODES and credit_review is None:
            continue
        return code
    return EscalationReasonCode.OTHER


def escalate_decision(
    ctx: TurnContext,
    decision: Decision,
    *,
    open_questions: tuple[str, ...] = (),
    card_request: CardRequest | None = None,
    case_ref: CaseId | None = None,
    credit_review: CreditReview | None = None,
) -> Step:
    code = escalation_code(decision, card_request=card_request, credit_review=credit_review)
    detail = ", ".join(decision.decisive_rule_ids) or "escalation"
    return escalate(
        ctx,
        code,
        detail,
        decision=decision,
        open_questions=open_questions,
        card_request=card_request,
        case_ref=case_ref,
        credit_review=credit_review,
    )


def blocking_step(ctx: TurnContext, decision: Decision, *, state: str, step_up_ok: bool = False) -> Step | None:
    """The step a decision forces (refusal, escalation, re-authentication, step-up), or ``None`` to go on."""
    kind = decision.kind
    auth = any(rule_id.startswith("AUTH.") for rule_id in decision.decisive_rule_ids)
    if kind is DecisionKind.REFUSE:
        return refuse(ctx, decision)
    if kind is DecisionKind.ESCALATE:
        return escalate_decision(ctx, decision)
    if kind is DecisionKind.DENY and auth:
        ctx.engine = ctx.engine.evolve(resume_state=state)
        return Step(AUTH_REQUIRED, Reply(template="common.auth_required", notices=REAUTH_NOTICES))
    if kind is DecisionKind.REQUIRE_STEP_UP and not step_up_ok:
        return step_up(ctx, state, because_of_risk=step_up_from_risk(ctx, decision))
    return None


def spend_clarification(ctx: TurnContext, *, open_questions: tuple[str, ...] = ()) -> Step | None:
    """Count one more clarifying question, or escalate when the budget is spent (``ESC.clarification_exhausted``)."""
    decision = evaluate(ctx, clarification_attempts=ctx.clarifications_used)
    exhausted = any(r.rule_id == "ESC.clarification_exhausted" and not r.passed for r in decision.rule_results)
    if not exhausted:
        ctx.clarifications_used += 1
        return None
    return escalate_decision(ctx, decision, open_questions=open_questions)
