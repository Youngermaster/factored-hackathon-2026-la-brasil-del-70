"""The synthetic eligibility service over the fixture pack: outcome mapping, labels, and invariants."""

from decimal import Decimal
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from bank_agent.domain.actions import ActionKind
from bank_agent.domain.credit import CreditProfile
from bank_agent.domain.eligibility import EligibilityOutcome, EligibilityView, ReviewReason, RiskBand
from bank_agent.domain.errors import EligibilityServiceUnavailableError, PolicyPackInvalidError
from bank_agent.domain.locale import Language, Locale
from bank_agent.domain.money import Currency, Money
from bank_agent.policy.eligibility import SyntheticEligibilityService, render_eligibility
from bank_agent.policy.pack import PolicyPack
from bank_agent.ports.eligibility import CreditApplicationFacts, EligibilityRequest
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.ids import SequentialIdGenerator
from bank_agent_builders import CUSTOMER_A, T0, a_date, risk_estimate
from bank_agent_credit import catalog_products
from bank_agent_policy import fixture_messages, fixture_pack

PACK = fixture_pack()
RANK = {
    EligibilityOutcome.INDICATIVELY_ELIGIBLE: 0,
    EligibilityOutcome.REVIEW_REQUIRED: 1,
    EligibilityOutcome.NOT_ELIGIBLE: 2,
    EligibilityOutcome.INSUFFICIENT_DATA: 3,
}


def service() -> SyntheticEligibilityService:
    return SyntheticEligibilityService(PACK, FixedClock(T0), SequentialIdGenerator())


def profile(**overrides: Any) -> CreditProfile | None:
    fields: dict[str, Any] = {
        "customer_id": CUSTOMER_A,
        "credit_score": 712,
        "estimated_monthly_income": Money.of("32000.00", Currency.MXN),
        "tenure_months": 52,
        "max_days_past_due": 0,
        "as_of": a_date(),
    }
    return CreditProfile.model_validate({**fields, **overrides})


def assessment_request(code: str = "MX-PL-FIXTURE", amount: str = "40000.00", **overrides: Any) -> EligibilityRequest:
    product = next(p for p in catalog_products() if p.product_code == code)
    fields: dict[str, Any] = {
        "product": product,
        "profile": profile(),
        "application": CreditApplicationFacts(
            requested_amount=Money.of(amount, product.currency), requested_term_months=24, purpose="general_purpose"
        ),
        "risk_estimate": risk_estimate(),
        "jurisdiction": product.jurisdiction,
        "as_of": T0,
    }
    return EligibilityRequest.model_validate({**fields, **overrides})


def test_a_clean_request_is_indicatively_eligible_and_labeled_synthetic() -> None:
    assessment = service().assess(assessment_request())
    assert assessment.outcome is EligibilityOutcome.INDICATIVELY_ELIGIBLE
    assert assessment.synthetic is True
    assert str(assessment.service) == f"eligibility:synthetic@{PACK.version}"
    assert assessment.rule_results[0].rule_id == "ELG.self_service_product"
    assert all(result.clause_refs for result in assessment.rule_results)


@pytest.mark.parametrize(
    ("overrides", "outcome", "reason"),
    [
        (
            {"profile": profile(credit_score=None)},
            EligibilityOutcome.INSUFFICIENT_DATA,
            ReviewReason.MISSING_CREDIT_SCORE,
        ),
        (
            {"profile": profile(estimated_monthly_income=None)},
            EligibilityOutcome.INSUFFICIENT_DATA,
            ReviewReason.MISSING_INCOME,
        ),
        ({"risk_estimate": None}, EligibilityOutcome.REVIEW_REQUIRED, ReviewReason.RISK_ESTIMATE_UNAVAILABLE),
        (
            {"profile": profile(max_days_past_due=12)},
            EligibilityOutcome.REVIEW_REQUIRED,
            ReviewReason.DAYS_PAST_DUE_PRESENT,
        ),
        ({"amount": "250000.00"}, EligibilityOutcome.REVIEW_REQUIRED, ReviewReason.AMOUNT_ABOVE_REVIEW_THRESHOLD),
    ],
)
def test_outcome_mapping(overrides: dict[str, Any], outcome: EligibilityOutcome, reason: ReviewReason) -> None:
    assessment = service().assess(assessment_request(**overrides))
    assert assessment.outcome is outcome
    assert reason in assessment.review_reasons


def test_a_failed_hard_rule_is_not_eligible() -> None:
    assessment = service().assess(assessment_request(profile=profile(credit_score=600)))
    assert assessment.outcome is EligibilityOutcome.NOT_ELIGIBLE
    assert assessment.review_reasons == ()


def test_review_dominates_a_failed_hard_rule() -> None:
    assessment = service().assess(assessment_request(profile=profile(credit_score=600), risk_estimate=None))
    assert assessment.outcome is EligibilityOutcome.REVIEW_REQUIRED


def test_a_mortgage_runs_only_the_self_service_rule() -> None:
    assessment = service().assess(assessment_request("CO-MG-FIXTURE", "90000000", profile=None, risk_estimate=None))
    assert assessment.outcome is EligibilityOutcome.REVIEW_REQUIRED
    assert [result.rule_id for result in assessment.rule_results] == ["ELG.self_service_product"]


def test_a_product_type_without_parameters_makes_the_service_unavailable() -> None:
    with pytest.raises(EligibilityServiceUnavailableError):
        service().assess(assessment_request("AR-PL-FIXTURE", "300000.00"))


def test_the_renderer_states_outcome_reasons_uncertainty_review_path_and_disclaimer() -> None:
    assessment = service().assess(assessment_request(profile=profile(estimated_monthly_income=None)))
    rendered = render_eligibility(PACK, EligibilityView.from_assessment(assessment), Language.PT, Locale.PT_BR)
    lines = rendered.text.splitlines()
    assert lines[0] == "[fixture pt] synthetic_notice"
    assert lines[1] == "[fixture pt] outcome insufficient_data"
    assert "- [fixture pt] missing monthly_income" in lines
    assert lines[-1] == "[fixture pt] CRE-ALL-1"
    assert rendered.citations[-1].clause_id == "CRE-ALL-1"


def test_the_renderer_refuses_approval_wording() -> None:
    assessment = service().assess(assessment_request())
    view = EligibilityView.from_assessment(assessment)
    messages = {language: fixture_messages(language) for language in Language}
    messages[Language.EN]["outcome"]["indicatively_eligible"] = "Pre-approved, congratulations"
    bad = PolicyPack(
        version=PACK.version,
        info=PACK.info,
        clauses={(cid, lang): [PACK.get_clause(cid, lang)] for cid in PACK.clause_ids() for lang in Language},
        bindings=PACK.bindings,
        matrix={kind: PACK.action_requirements(kind) for kind in ActionKind},
        messages=messages,
    )
    with pytest.raises(PolicyPackInvalidError):
        render_eligibility(bad, view, Language.EN, Locale.EN_US)


estimates = st.builds(
    lambda low, width, band: risk_estimate(
        probability=Decimal(low) / 1000,
        interval_low=Decimal(low) / 1000,
        interval_high=Decimal(low + width) / 1000,
        band=band,
    ),
    st.integers(0, 900),
    st.integers(0, 99),
    st.sampled_from([RiskBand.LOW, RiskBand.MEDIUM, RiskBand.HIGH]),
)
profiles = st.builds(
    lambda score, income, tenure, dpd: profile(
        credit_score=score,
        estimated_monthly_income=None if income is None else Money.of(f"{income}.00", Currency.MXN),
        tenure_months=tenure,
        max_days_past_due=dpd,
    ),
    st.one_of(st.none(), st.integers(300, 850)),
    st.one_of(st.none(), st.integers(0, 90000)),
    st.one_of(st.none(), st.integers(0, 120)),
    st.one_of(st.none(), st.integers(0, 60)),
)


@settings(max_examples=200, deadline=None)
@given(st.one_of(st.none(), profiles), st.one_of(st.none(), estimates), st.integers(5000, 320000))
def test_never_indicatively_eligible_with_a_missing_fact_estimate_or_straddled_cut(
    value: CreditProfile | None, estimate: Any, amount: int
) -> None:
    assessment = service().assess(assessment_request(amount=f"{amount}.00", profile=value, risk_estimate=estimate))
    straddles = estimate is not None and any(
        estimate.interval_low <= cut <= estimate.interval_high for cut in (Decimal("0.20"), Decimal("0.35"))
    )
    missing = value is None or bool(value.missing_facts())
    if missing or estimate is None or straddles:
        assert assessment.outcome is not EligibilityOutcome.INDICATIVELY_ELIGIBLE
    if assessment.outcome is EligibilityOutcome.INDICATIVELY_ELIGIBLE:
        assert not assessment.review_reasons
        assert not assessment.missing_facts


@settings(max_examples=200, deadline=None)
@given(profiles, estimates)
def test_a_worse_risk_band_never_improves_the_outcome(value: CreditProfile | None, estimate: Any) -> None:
    outcomes = [
        service()
        .assess(assessment_request(profile=value, risk_estimate=estimate.model_copy(update={"band": band})))
        .outcome
        for band in (RiskBand.LOW, RiskBand.MEDIUM, RiskBand.HIGH)
    ]
    ranks = [RANK[outcome] for outcome in outcomes]
    assert ranks == sorted(ranks)
