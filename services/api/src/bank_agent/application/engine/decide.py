"""Calls to the policy kernel from handlers. Every decision is recorded with its rule ids and clause versions.

Facts come only from verified records, detectors, and the session: the jurisdiction from the verified customer, the
data as-of date from settings, the trust state from the session lineage, and the signals the engine detected. The
kernel is pure; this module only builds the request.
"""

from bank_agent.application.engine.context import TurnContext
from bank_agent.domain.actions import ActionRequest
from bank_agent.domain.decision import ClauseRef, Decision, DecisionKind
from bank_agent.domain.workflow import CROSS_WORKFLOW_INTENTS, Intent
from bank_agent.policy.explain import decision_refs
from bank_agent.policy.facts import AccountFacts, CardFacts, CreditFacts, DisputeFacts, EvaluationRequest, PolicyFacts


def evaluate(
    ctx: TurnContext,
    *,
    policy_state: str | None = None,
    intent: Intent | None = None,
    action: ActionRequest | None = None,
    dispute: DisputeFacts | None = None,
    card: CardFacts | None = None,
    account: AccountFacts | None = None,
    credit: CreditFacts | None = None,
    clarification_attempts: int = 0,
    tool_failures: int = 0,
    verification_mismatch: bool = False,
    eligibility_contested: bool = False,
) -> Decision:
    chosen_intent = intent if intent is not None else current_intent(ctx)
    facts = PolicyFacts(
        jurisdiction=ctx.customer.country,
        data_as_of=ctx.services.policy.data_as_of,
        intent=chosen_intent,
        privacy=ctx.privacy,
        escalation=ctx.escalation.evolve(
            clarification_attempts=clarification_attempts,
            tool_failures_after_retries=tool_failures,
            verification_mismatch=verification_mismatch,
            eligibility_contested=eligibility_contested,
        ),
        account=account,
        dispute=dispute,
        card=card,
        credit=credit,
    )
    request = EvaluationRequest(
        workflow=ctx.workflow,
        state=policy_state or ctx.policy_state,
        action=action,
        session=ctx.snapshot,
        trust=ctx.trust,
        facts=facts,
    )
    return ctx.recorder.decision(ctx.services.policy.evaluate(request))


def current_intent(ctx: TurnContext) -> Intent | None:
    """The newest prediction when this workflow owns it (or it is cross-workflow), else the served intent."""
    predicted = ctx.prediction.intent if ctx.prediction is not None else None
    if predicted is not None and (predicted in ctx.definition.intents or predicted in CROSS_WORKFLOW_INTENTS):
        return predicted
    return ctx.engine.intent


def explanation(decision: Decision) -> tuple[ClauseRef, ...]:
    """The clauses that explain ``decision`` (its decisive rules' clauses)."""
    return tuple(decision_refs(decision))


def failed(decision: Decision, rule_id: str) -> bool:
    return any(result.rule_id == rule_id and not result.passed for result in decision.rule_results)


def clarification_left(ctx: TurnContext) -> bool:
    """True while another clarifying question fits the budget (``ESC.clarification_exhausted`` decides).

    Degraded (L2 or L3), the kernel sees one more attempt than was made: one question fewer before a handoff,
    because the deterministic understanding that serves then is less likely to resolve an unclear request.
    """
    stricter = 1 if ctx.degradation.stricter_clarification else 0
    decision = evaluate(ctx, clarification_attempts=ctx.clarifications_used + stricter)
    return not failed(decision, "ESC.clarification_exhausted")


_PRECEDENCE = (
    DecisionKind.REFUSE,
    DecisionKind.ESCALATE,
    DecisionKind.DENY,
    DecisionKind.ABSTAIN,
    DecisionKind.CLARIFY,
)


def beyond_step_up(decision: Decision) -> DecisionKind:
    """The decision without its step-up request: authentication outranks everything in the kernel, so a pending
    step-up can hide that the action would be denied or abstained anyway (an already blocked card)."""
    if decision.kind is not DecisionKind.REQUIRE_STEP_UP:
        return decision.kind
    effects = {r.effect for r in decision.rule_results if not r.passed and r.effect is not DecisionKind.REQUIRE_STEP_UP}
    return next((kind for kind in _PRECEDENCE if kind in effects), DecisionKind.REQUIRE_STEP_UP)
