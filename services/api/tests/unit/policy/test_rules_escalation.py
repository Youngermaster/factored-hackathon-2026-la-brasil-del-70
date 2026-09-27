"""ESC rules: each trigger escalates, and its absence passes."""

from typing import Any

import pytest

from bank_agent.domain.decision import DecisionKind
from bank_agent.domain.eligibility import EligibilityOutcome
from bank_agent.domain.trust import TrustEventKind
from bank_agent.policy.facts import CreditFacts, EscalationSignals
from bank_agent.policy.rules import CONVERSATION_RULES, RuleContext
from bank_agent_policy import FIXTURE_CLAUSES, context, facts, request, trust

ESC_PARAMS = FIXTURE_CLAUSES["ESC-ALL-1"][0]


def run(rule_id: str, ctx: RuleContext) -> tuple[bool, str, DecisionKind | None]:
    result = CONVERSATION_RULES[rule_id].run(ctx, ())
    return result.passed, result.reason_code, result.effect


def signals(**fields: Any) -> RuleContext:
    return context(ESC_PARAMS, request_=request(facts_=facts(escalation=EscalationSignals.model_validate(fields))))


@pytest.mark.parametrize(
    ("rule_id", "fields", "reason"),
    [
        ("ESC.human_requested", {"human_requested": True}, "human_requested"),
        ("ESC.legal_or_regulator_mention", {"legal_or_regulator_mention": True}, "legal_or_regulator_mention"),
        ("ESC.distress_signal", {"distress_signal": True}, "distress_signal"),
        ("ESC.clarification_exhausted", {"clarification_attempts": 2}, "clarification_exhausted"),
        ("ESC.tool_failure_exhausted", {"tool_failures_after_retries": 1}, "tool_failure"),
        ("ESC.verification_mismatch", {"verification_mismatch": True}, "verification_mismatch"),
        ("ESC.repeat_complainer", {"prior_complaints_in_lookback": 3}, "repeat_complainer"),
        ("ESC.eligibility_contested", {"eligibility_contested": True}, "eligibility_contested"),
    ],
)
def test_each_trigger_escalates_and_its_absence_passes(rule_id: str, fields: dict[str, Any], reason: str) -> None:
    assert run(rule_id, signals(**fields)) == (False, reason, DecisionKind.ESCALATE)
    assert run(rule_id, signals())[0] is True


@pytest.mark.parametrize(("attempts", "passed"), [(0, True), (1, True), (2, False)])
def test_clarification_budget_boundary(attempts: int, passed: bool) -> None:
    assert run("ESC.clarification_exhausted", signals(clarification_attempts=attempts))[0] is passed


@pytest.mark.parametrize(("count", "passed"), [(2, True), (3, False)])
def test_repeat_complainer_threshold(count: int, passed: bool) -> None:
    assert run("ESC.repeat_complainer", signals(prior_complaints_in_lookback=count))[0] is passed


def test_only_a_high_risk_tier_escalates() -> None:
    elevated = context(request_=request(trust_=trust(TrustEventKind.INJECTION_DETECTED)))
    assert run("ESC.risk_tier_high", elevated)[0] is True
    high = context(request_=request(trust_=trust(TrustEventKind.CROSS_CUSTOMER_PROBE)))
    assert run("ESC.risk_tier_high", high) == (False, "risk_tier_high", DecisionKind.ESCALATE)


@pytest.mark.parametrize(
    ("outcome", "passed"),
    [
        (EligibilityOutcome.REVIEW_REQUIRED, False),
        (EligibilityOutcome.INSUFFICIENT_DATA, True),
        (EligibilityOutcome.INDICATIVELY_ELIGIBLE, True),
        (None, True),
    ],
)
def test_credit_review_required(outcome: EligibilityOutcome | None, passed: bool) -> None:
    ctx = context(request_=request(facts_=facts(credit=CreditFacts(eligibility_outcome=outcome))))
    assert run("ESC.credit_review_required", ctx)[0] is passed
