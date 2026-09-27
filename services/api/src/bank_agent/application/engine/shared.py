"""Shared outcomes every workflow uses: escalate, abstain, refuse, out of scope, greeting, informational, step-up.

Each builds a ``Step`` from verified state and clause references; none writes customer text by hand.
"""

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.decide import current_intent, evaluate, explanation
from bank_agent.application.engine.definition import (
    ABSTAINED,
    AUTH_REQUIRED,
    ESCALATED,
    REFUSED,
    UnsupportedRequest,
)
from bank_agent.application.engine.handoff import HandoffBuilder, HandoffPlan
from bank_agent.application.engine.reply import Param, Reply
from bank_agent.application.engine.templates.labels import CAPABILITIES, join
from bank_agent.application.grounding.retrieval import RetrievalDecision
from bank_agent.domain.cards import CardRequest
from bank_agent.domain.conversation import EscalationNotice, NoticeCode
from bank_agent.domain.decision import ClauseRef, Decision, DecisionKind
from bank_agent.domain.eligibility import CreditReview
from bank_agent.domain.errors import ConfigurationError
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.execution_record import RetrievalDecisionCode, RetrievalRecord
from bank_agent.domain.identifiers import CaseId
from bank_agent.domain.locale import Language
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
    return Step(REFUSED, Reply(template=template, explain=explanation(decision)), Outcome.REFUSED)


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


def informational(ctx: TurnContext) -> Step:
    """Open retrieval (informational intent only): the cited clauses, or a clause-backed abstention."""
    evaluate(ctx, policy_state="START", intent=Intent.INFORMATIONAL)
    try:
        outcome = ctx.services.informational.search(
            intent=Intent.INFORMATIONAL, text=ctx.text, customer=ctx.customer, language=ctx.language
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


def step_up(ctx: TurnContext, state: str) -> Step:
    reply = Reply(template="common.step_up_required", step_up_required=True)
    return Step(state, reply, Outcome.IN_PROGRESS)


def escalation_code(decision: Decision) -> EscalationReasonCode:
    """The handoff reason for an ``escalate`` decision, from its first decisive rule."""
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
        if rule_id in codes:
            return codes[rule_id]
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
    code = escalation_code(decision)
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
        return step_up(ctx, state)
    return None


def spend_clarification(ctx: TurnContext, *, open_questions: tuple[str, ...] = ()) -> Step | None:
    """Count one more clarifying question, or escalate when the budget is spent (``ESC.clarification_exhausted``)."""
    decision = evaluate(ctx, clarification_attempts=ctx.clarifications_used)
    exhausted = any(r.rule_id == "ESC.clarification_exhausted" and not r.passed for r in decision.rule_results)
    if not exhausted:
        ctx.clarifications_used += 1
        return None
    return escalate_decision(ctx, decision, open_questions=open_questions)
