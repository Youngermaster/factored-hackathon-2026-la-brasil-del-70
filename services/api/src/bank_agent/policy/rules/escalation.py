"""ESC rules: the triggers that send a conversation to a human. Any trigger prevents automatic resolution."""

from bank_agent.domain.decision import DecisionKind
from bank_agent.domain.eligibility import EligibilityOutcome
from bank_agent.domain.trust import RiskTier
from bank_agent.policy.rules.context import CONVERSATION_RULES as RULES
from bank_agent.policy.rules.context import RuleContext
from bank_agent.policy.rules.registry import Verdict, typed_param


def _trigger(detected: bool, reason: str, quiet: str, **params: int) -> Verdict:
    if detected:
        return Verdict(passed=False, reason_code=reason, effect=DecisionKind.ESCALATE, params=params)
    return Verdict(passed=True, reason_code=quiet, params=params)


@RULES.rule("ESC.human_requested", version=1, reasons=("no_human_request", "human_requested"))
def human_requested(context: RuleContext) -> Verdict:
    return _trigger(context.facts.escalation.human_requested, "human_requested", "no_human_request")


@RULES.rule("ESC.legal_or_regulator_mention", version=1, reasons=("no_legal_mention", "legal_or_regulator_mention"))
def legal_or_regulator_mention(context: RuleContext) -> Verdict:
    signals = context.facts.escalation
    return _trigger(signals.legal_or_regulator_mention, "legal_or_regulator_mention", "no_legal_mention")


@RULES.rule("ESC.distress_signal", version=1, reasons=("no_distress_signal", "distress_signal"))
def distress_signal(context: RuleContext) -> Verdict:
    return _trigger(context.facts.escalation.distress_signal, "distress_signal", "no_distress_signal")


@RULES.rule(
    "ESC.clarification_exhausted",
    version=1,
    params={"clarification_budget": int},
    reasons=("clarification_budget_left", "clarification_exhausted"),
)
def clarification_exhausted(context: RuleContext) -> Verdict:
    budget = typed_param(context.params, "clarification_budget", int)
    attempts = context.facts.escalation.clarification_attempts
    return _trigger(
        attempts >= budget, "clarification_exhausted", "clarification_budget_left", clarification_budget=budget
    )


@RULES.rule(
    "ESC.tool_failure_exhausted",
    version=1,
    params={"tool_retry_budget": int},
    reasons=("no_tool_failure", "tool_failure"),
)
def tool_failure_exhausted(context: RuleContext) -> Verdict:
    budget = typed_param(context.params, "tool_retry_budget", int)
    failures = context.facts.escalation.tool_failures_after_retries
    return _trigger(failures > 0, "tool_failure", "no_tool_failure", tool_retry_budget=budget)


@RULES.rule("ESC.verification_mismatch", version=1, reasons=("no_verification_mismatch", "verification_mismatch"))
def verification_mismatch(context: RuleContext) -> Verdict:
    mismatch = context.facts.escalation.verification_mismatch
    return _trigger(mismatch, "verification_mismatch", "no_verification_mismatch")


@RULES.rule(
    "ESC.repeat_complainer",
    version=1,
    params={"repeat_complaint_threshold": int, "repeat_complaint_lookback_days": int},
    reasons=("not_a_repeat_complainer", "repeat_complainer"),
)
def repeat_complainer(context: RuleContext) -> Verdict:
    threshold = typed_param(context.params, "repeat_complaint_threshold", int)
    lookback = typed_param(context.params, "repeat_complaint_lookback_days", int)
    count = context.facts.escalation.prior_complaints_in_lookback
    return _trigger(
        count >= threshold,
        "repeat_complainer",
        "not_a_repeat_complainer",
        repeat_complaint_threshold=threshold,
        repeat_complaint_lookback_days=lookback,
    )


@RULES.rule("ESC.risk_tier_high", version=1, reasons=("risk_tier_not_high", "risk_tier_high"))
def risk_tier_high(context: RuleContext) -> Verdict:
    return _trigger(context.request.risk_tier is RiskTier.HIGH, "risk_tier_high", "risk_tier_not_high")


@RULES.rule("ESC.credit_review_required", version=1, reasons=("no_credit_review", "credit_review_required"))
def credit_review_required(context: RuleContext) -> Verdict:
    credit = context.facts.credit
    review = credit is not None and credit.eligibility_outcome is EligibilityOutcome.REVIEW_REQUIRED
    return _trigger(review, "credit_review_required", "no_credit_review")


@RULES.rule("ESC.eligibility_contested", version=1, reasons=("not_contested", "eligibility_contested"))
def eligibility_contested(context: RuleContext) -> Verdict:
    return _trigger(context.facts.escalation.eligibility_contested, "eligibility_contested", "not_contested")
