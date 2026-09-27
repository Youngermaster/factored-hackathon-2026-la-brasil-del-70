"""Calls to the policy kernel from handlers. Every decision is recorded with its rule ids and clause versions.

Facts come only from verified records, detectors, and the session: the jurisdiction from the verified customer, the
data as-of date from settings, the trust state from the session lineage, and the signals the engine detected. The
kernel is pure; this module only builds the request.
"""

from bank_agent.application.engine.context import TurnContext
from bank_agent.domain.actions import ActionRequest
from bank_agent.domain.decision import ClauseRef, Decision
from bank_agent.domain.workflow import Intent
from bank_agent.policy.explain import decision_refs
from bank_agent.policy.facts import CardFacts, DisputeFacts, EvaluationRequest, PolicyFacts


def evaluate(
    ctx: TurnContext,
    *,
    policy_state: str | None = None,
    intent: Intent | None = None,
    action: ActionRequest | None = None,
    dispute: DisputeFacts | None = None,
    card: CardFacts | None = None,
    clarification_attempts: int = 0,
    tool_failures: int = 0,
    verification_mismatch: bool = False,
) -> Decision:
    chosen_intent = intent if intent is not None else (ctx.prediction.intent if ctx.prediction else None)
    facts = PolicyFacts(
        jurisdiction=ctx.customer.country,
        data_as_of=ctx.services.policy.data_as_of,
        intent=chosen_intent,
        privacy=ctx.privacy,
        escalation=ctx.escalation.evolve(
            clarification_attempts=clarification_attempts,
            tool_failures_after_retries=tool_failures,
            verification_mismatch=verification_mismatch,
        ),
        dispute=dispute,
        card=card,
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


def explanation(decision: Decision) -> tuple[ClauseRef, ...]:
    """The clauses that explain ``decision`` (its decisive rules' clauses)."""
    return tuple(decision_refs(decision))


def failed(decision: Decision, rule_id: str) -> bool:
    return any(result.rule_id == rule_id and not result.passed for result in decision.rule_results)


def clarification_left(ctx: TurnContext) -> bool:
    """True while another clarifying question fits the budget (``ESC.clarification_exhausted`` decides)."""
    decision = evaluate(ctx, clarification_attempts=ctx.clarifications_used)
    return not failed(decision, "ESC.clarification_exhausted")
