"""ELG rules, called directly: boundaries, missing facts, and the monthly payment."""

from decimal import Decimal
from typing import Any

import pytest

from bank_agent.domain.credit import CreditProfile
from bank_agent.domain.decision import DecisionKind
from bank_agent.domain.eligibility import RiskBand, UncertaintyFlag
from bank_agent.domain.money import Currency, Money
from bank_agent.policy.rules import ELIGIBILITY_RULES, EligibilityContext
from bank_agent.policy.rules.eligibility import monthly_payment
from bank_agent.ports.eligibility import CreditApplicationFacts, EligibilityRequest
from bank_agent_builders import CUSTOMER_A, T0, a_date, risk_estimate
from bank_agent_credit import catalog_products
from bank_agent_policy import FIXTURE_CLAUSES

LOAN_PARAMS: dict[str, Any] = {**FIXTURE_CLAUSES["ELG-MX-1.2"][0], **FIXTURE_CLAUSES["ELG-ALL-2"][0]}
CARD_PARAMS: dict[str, Any] = {**FIXTURE_CLAUSES["ELG-MX-1.1"][0], **FIXTURE_CLAUSES["ELG-ALL-2"][0]}


def profile(**overrides: Any) -> CreditProfile:
    fields: dict[str, Any] = {
        "customer_id": CUSTOMER_A,
        "credit_score": 712,
        "estimated_monthly_income": Money.of("32000.00", Currency.MXN),
        "tenure_months": 52,
        "max_days_past_due": 0,
        "as_of": a_date(),
    }
    return CreditProfile.model_validate({**fields, **overrides})


def ctx(code: str = "MX-PL-FIXTURE", amount: str = "40000.00", term: int = 24, **overrides: Any) -> EligibilityContext:
    product = next(p for p in catalog_products() if p.product_code == code)
    income = overrides.pop("declared_income", None)
    fields: dict[str, Any] = {
        "product": product,
        "profile": profile(),
        "application": CreditApplicationFacts(
            requested_amount=Money.of(amount, product.currency),
            requested_term_months=term,
            purpose=overrides.pop("purpose", "general_purpose"),
            declared_monthly_income=income,
        ),
        "risk_estimate": risk_estimate(),
        "jurisdiction": product.jurisdiction,
        "as_of": T0,
    }
    request = EligibilityRequest.model_validate({**fields, **overrides})
    params = CARD_PARAMS if product.product_type.value == "credit_card" else LOAN_PARAMS
    return EligibilityContext(request=request, params=params)


def run(rule_id: str, context: EligibilityContext) -> tuple[bool, str, DecisionKind | None, tuple[str, ...]]:
    result = ELIGIBILITY_RULES[rule_id].run(context, ())
    return result.passed, result.reason_code, result.effect, result.missing_facts


def test_a_mortgage_needs_a_human_assessment() -> None:
    assert run("ELG.self_service_product", ctx("CO-MG-FIXTURE", "90000000", 120))[1:3] == (
        "product_requires_human_assessment",
        DecisionKind.ESCALATE,
    )
    assert run("ELG.self_service_product", ctx())[0]


@pytest.mark.parametrize(("score", "passed"), [(649, False), (650, True), (651, True)])
def test_credit_score_minimum_boundary(score: int, passed: bool) -> None:
    assert run("ELG.credit_score_minimum", ctx(profile=profile(credit_score=score)))[0] is passed


@pytest.mark.parametrize("rule_id", ["ELG.credit_score_present", "ELG.credit_score_minimum"])
def test_a_missing_score_is_a_missing_fact(rule_id: str) -> None:
    assert run(rule_id, ctx(profile=profile(credit_score=None)))[3] == ("credit_score",)
    assert run(rule_id, ctx(profile=None))[3] == ("credit_score",)


def test_income_comes_from_the_profile_or_the_declaration() -> None:
    no_income = profile(estimated_monthly_income=None)
    assert run("ELG.income_present", ctx(profile=no_income))[3] == ("monthly_income",)
    declared = ctx(profile=no_income, declared_income=Money.of("30000.00", Currency.MXN))
    assert run("ELG.income_present", declared)[0]
    other_currency = profile(estimated_monthly_income=Money.of("1000.00", Currency.USD))
    assert run("ELG.income_present", ctx(profile=other_currency))[1] == "income_currency_mismatch"
    assert run("ELG.payment_to_income_max", ctx(profile=other_currency))[3] == ("monthly_income",)


def test_loan_payment_is_the_annuity_at_the_maximum_rate() -> None:
    payment = monthly_payment(ctx())
    assert Decimal("3130") < payment < Decimal("3150")


def test_card_payment_is_a_percentage_of_the_limit() -> None:
    assert monthly_payment(ctx("MX-CC-FIXTURE", "60000.00", 12)) == Decimal("3000")


def test_payment_to_income_boundary() -> None:
    at_limit = profile(estimated_monthly_income=Money.of("8571.43", Currency.MXN))
    assert run("ELG.payment_to_income_max", ctx("MX-CC-FIXTURE", "60000.00", 12, profile=at_limit))[0]
    below = profile(estimated_monthly_income=Money.of("8571.42", Currency.MXN))
    assert run("ELG.payment_to_income_max", ctx("MX-CC-FIXTURE", "60000.00", 12, profile=below))[2] is DecisionKind.DENY
    zero = profile(estimated_monthly_income=Money.of("0", Currency.MXN))
    assert run("ELG.payment_to_income_max", ctx(profile=zero))[1] == "payment_to_income_above_maximum"


def test_days_past_due_asks_for_review_and_tenure_is_a_hard_rule() -> None:
    assert run("ELG.days_past_due_max", ctx(profile=profile(max_days_past_due=1)))[2] is DecisionKind.ESCALATE
    assert run("ELG.days_past_due_max", ctx(profile=profile(max_days_past_due=None)))[3] == ("max_days_past_due",)
    assert run("ELG.tenure_minimum", ctx(profile=profile(tenure_months=11)))[2] is DecisionKind.DENY
    assert run("ELG.tenure_minimum", ctx(profile=profile(tenure_months=12)))[0]
    assert run("ELG.tenure_minimum", ctx(profile=profile(tenure_months=None)))[3] == ("tenure_months",)


@pytest.mark.parametrize(
    ("amount", "term", "purpose", "reason"),
    [
        ("10000.00", 24, "general_purpose", "amount_within_product_range"),
        ("9999.99", 24, "general_purpose", "amount_outside_product_range"),
        ("300000.01", 24, "general_purpose", "amount_outside_product_range"),
        ("40000.00", 49, "general_purpose", "term_outside_product_range"),
        ("40000.00", 24, "home_purchase", "purpose_not_offered"),
        ("200000.00", 24, "general_purpose", "amount_within_product_range"),
        ("200000.01", 24, "general_purpose", "amount_above_review_threshold"),
    ],
)
def test_amount_term_and_purpose(amount: str, term: int, purpose: str, reason: str) -> None:
    assert run("ELG.amount_within_product_range", ctx(amount=amount, term=term, purpose=purpose))[1] == reason


def test_risk_estimate_rules() -> None:
    for rule_id in ("ELG.risk_estimate_available", "ELG.risk_band_acceptable", "ELG.risk_interval_not_borderline"):
        assert run(rule_id, ctx(risk_estimate=None))[1:3] == ("risk_estimate_unavailable", DecisionKind.ESCALATE)
        unknown = risk_estimate(band=RiskBand.UNKNOWN, flags=[UncertaintyFlag.MODEL_UNAVAILABLE])
        assert run(rule_id, ctx(risk_estimate=unknown))[1] == "risk_estimate_unavailable"
        assert run(rule_id, ctx())[0]
    high = risk_estimate(
        band=RiskBand.HIGH, probability=Decimal("0.50"), interval_low=Decimal("0.45"), interval_high=Decimal("0.55")
    )
    assert run("ELG.risk_band_acceptable", ctx(risk_estimate=high))[2] is DecisionKind.DENY


@pytest.mark.parametrize(
    ("low", "high", "borderline"),
    [
        ("0.08", "0.19", False),
        ("0.08", "0.1901", True),
        ("0.2099", "0.30", True),
        ("0.21", "0.30", False),
        ("0.15", "0.25", True),
        ("0.3599", "0.40", True),
        ("0.36", "0.40", False),
    ],
)
def test_borderline_interval_uses_the_cut_points_and_the_margin(low: str, high: str, borderline: bool) -> None:
    estimate = risk_estimate(probability=Decimal(low), interval_low=Decimal(low), interval_high=Decimal(high))
    assert (not run("ELG.risk_interval_not_borderline", ctx(risk_estimate=estimate))[0]) is borderline
