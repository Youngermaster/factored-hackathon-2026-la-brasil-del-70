import re
from decimal import Decimal
from typing import Any, get_args

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from bank_agent.domain.base import internal_fields
from bank_agent.domain.credit import CreditProductType
from bank_agent.domain.decision import DecisionKind
from bank_agent.domain.eligibility import (
    CreditReview,
    CreditRiskFeatures,
    EligibilityAssessmentRecord,
    EligibilityOutcome,
    EligibilityView,
    ReviewPath,
    ReviewReason,
    RiskBand,
    RiskEstimate,
    RiskEstimateRecord,
    ServiceRef,
    UncertaintyFlag,
    UncertaintyStatement,
)
from bank_agent.domain.locale import Country
from bank_agent_builders import elg_rule, eligibility_assessment, risk_estimate

PROTECTED_OR_PROXY = re.compile(
    r"gender|sex|birth|(^|_)age($|_)|marital|accent|city|state|postal|address|latitude|longitude|"
    r"segment|occupation|education|name|document|email|phone|customer"
)


# --- Features ------------------------------------------------------------------------------------------------


def test_features_exclude_protected_and_proxy_attributes_by_construction() -> None:
    offending = [name for name in CreditRiskFeatures.model_fields if PROTECTED_OR_PROXY.search(name)]
    assert offending == []


def test_features_carry_no_free_text() -> None:
    for name, field in CreditRiskFeatures.model_fields.items():
        assert str not in (field.annotation, *get_args(field.annotation)), name


def test_features_report_missing_values_and_reject_floats() -> None:
    features = CreditRiskFeatures(
        jurisdiction=Country.MX,
        product_type=CreditProductType.PERSONAL_LOAN,
        requested_term_months=24,
        credit_score=700,
    )
    assert "monthly_income_usd" in features.missing()
    assert "credit_score" not in features.missing()
    with pytest.raises(ValidationError):
        CreditRiskFeatures.model_validate(
            {"jurisdiction": "MX", "product_type": "personal_loan", "requested_term_months": 24, "utilization": 0.3}
        )


# --- Risk estimates ------------------------------------------------------------------------------------------


def test_builds_a_synthetic_internal_estimate() -> None:
    estimate = risk_estimate()
    assert estimate.synthetic_data is True
    assert estimate.ref.estimate_id == "rsk-000001"
    assert {"probability", "interval_low", "interval_high", "band"} <= internal_fields(RiskEstimate)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"interval_low": Decimal("0.2")}, "low <= probability"),
        ({"interval_high": Decimal("0.1")}, "low <= probability"),
        ({"band": RiskBand.UNKNOWN}, "unknown band"),
        ({"flags": ["wide_interval", "wide_interval"]}, "must not repeat"),
        ({"model": "router:fixture@1"}, "risk_estimator"),
    ],
)
def test_rejects_inconsistent_estimates(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        risk_estimate(**overrides)


def test_probabilities_stay_in_the_unit_interval_and_are_never_floats() -> None:
    with pytest.raises(ValidationError):
        risk_estimate(interval_high=Decimal("1.2"))
    with pytest.raises(ValidationError):
        risk_estimate(probability=0.12)


def test_an_unknown_band_is_allowed_with_a_quality_flag() -> None:
    estimate = risk_estimate(band=RiskBand.UNKNOWN, flags=[UncertaintyFlag.MISSING_FEATURES])
    assert estimate.band is RiskBand.UNKNOWN


# --- Assessments ---------------------------------------------------------------------------------------------


def test_builds_an_indicatively_eligible_assessment() -> None:
    assessment = eligibility_assessment()
    assert assessment.synthetic is True
    assert str(assessment.service) == "eligibility:synthetic@pack-fixture-1"


def _failed(**overrides: Any) -> Any:
    return elg_rule(passed=False, **overrides)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"rule_results": [elg_rule(rule_id="DSP.within_window")]}, "ELG rules only"),
        ({"review_reasons": ["missing_income"]}, "indicatively_eligible"),
        ({"missing_facts": ["credit_score"]}, "indicatively_eligible"),
        ({"rule_results": [_failed()]}, "indicatively_eligible"),
        ({"outcome": "review_required"}, "review reason or a missing fact"),
        ({"outcome": "insufficient_data", "review_reasons": ["missing_income"]}, "missing fact"),
        ({"outcome": "not_eligible"}, "failed rule with a clause"),
        ({"outcome": "not_eligible", "rule_results": [_failed(clause_refs=[])]}, "failed rule with a clause"),
        ({"review_reasons": ["missing_income", "missing_income"], "outcome": "review_required"}, "repeat"),
        (
            {"outcome": "review_required", "rule_results": [_failed(missing_facts=["income"], effect="escalate")]},
            "include every rule",
        ),
    ],
)
def test_rejects_inconsistent_assessments(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        eligibility_assessment(**overrides)


def test_valid_review_and_ineligible_assessments() -> None:
    review = eligibility_assessment(outcome="review_required", review_reasons=["borderline_risk_interval"])
    assert review.outcome is EligibilityOutcome.REVIEW_REQUIRED
    missing = eligibility_assessment(
        outcome="insufficient_data",
        rule_results=[_failed(effect=DecisionKind.ESCALATE, missing_facts=["estimated_monthly_income"])],
        missing_facts=["estimated_monthly_income"],
        review_reasons=["missing_income"],
    )
    assert missing.missing_facts == ("estimated_monthly_income",)
    assert (
        eligibility_assessment(outcome="not_eligible", rule_results=[_failed()]).outcome
        is EligibilityOutcome.NOT_ELIGIBLE
    )


@given(
    st.sampled_from(list(EligibilityOutcome)),
    st.lists(st.sampled_from(["credit_score", "estimated_monthly_income", "tenure_months"]), min_size=1, unique=True),
    st.lists(st.sampled_from(list(ReviewReason)), unique=True),
)
def test_an_assessment_with_a_missing_fact_is_never_indicatively_eligible(
    outcome: EligibilityOutcome, missing: list[str], reasons: list[ReviewReason]
) -> None:
    try:
        assessment = eligibility_assessment(
            outcome=outcome,
            missing_facts=missing,
            review_reasons=reasons,
            rule_results=[_failed(effect=DecisionKind.ESCALATE, missing_facts=missing)],
        )
    except ValidationError:
        return
    assert assessment.outcome is not EligibilityOutcome.INDICATIVELY_ELIGIBLE


def test_service_references_round_trip_and_are_not_model_references() -> None:
    ref = ServiceRef.model_validate("eligibility:synthetic@pack-3f2a")
    assert (ref.name, ref.version) == ("synthetic", "pack-3f2a")
    assert ServiceRef.model_validate_json(f'"{ref}"') == ref
    with pytest.raises(ValidationError, match="eligibility:name@version"):
        ServiceRef.model_validate("risk_estimator:fixture@1")


# --- Customer view -------------------------------------------------------------------------------------------


def test_the_customer_view_has_no_estimate_or_profile_field() -> None:
    forbidden = re.compile(r"probab|interval|band|estimate|score|income|risk|past_due|utilization")
    assert [name for name in EligibilityView.model_fields if forbidden.search(name)] == []


def test_view_of_an_eligible_assessment_offers_human_review() -> None:
    view = EligibilityView.from_assessment(eligibility_assessment())
    assert view.review_path is ReviewPath.SUBMIT_FOR_HUMAN_REVIEW
    assert view.uncertainty is UncertaintyStatement.INDICATIVE_ONLY
    assert view.disclaimer == "indicative_not_an_offer_or_decision"
    assert [str(reason.clause) for reason in view.reasons] == ["ELG-MX-1.1@1"]


@pytest.mark.parametrize(
    ("reasons", "statement"),
    [
        (["risk_estimate_unavailable"], UncertaintyStatement.ESTIMATE_UNAVAILABLE),
        (["borderline_risk_interval"], UncertaintyStatement.BORDERLINE_ESTIMATE),
        (["product_requires_human_assessment"], UncertaintyStatement.INDICATIVE_ONLY),
    ],
)
def test_view_of_a_review_states_its_uncertainty(reasons: list[str], statement: UncertaintyStatement) -> None:
    view = EligibilityView.from_assessment(eligibility_assessment(outcome="review_required", review_reasons=reasons))
    assert view.uncertainty is statement
    assert view.review_path is ReviewPath.REQUEST_HUMAN_CONTACT


def test_view_of_missing_data_asks_for_it() -> None:
    assessment = eligibility_assessment(outcome="insufficient_data", missing_facts=["estimated_monthly_income"])
    view = EligibilityView.from_assessment(assessment)
    assert view.review_path is ReviewPath.PROVIDE_MISSING_INFORMATION
    assert view.missing_facts == ("estimated_monthly_income",)
    with pytest.raises(ValidationError, match="asks for the missing information"):
        view.evolve(review_path=ReviewPath.REQUEST_HUMAN_CONTACT)


def test_view_of_a_not_eligible_result_offers_a_human() -> None:
    view = EligibilityView.from_assessment(eligibility_assessment(outcome="not_eligible", rule_results=[_failed()]))
    assert view.review_path is ReviewPath.REQUEST_HUMAN_CONTACT
    assert view.reasons[0].reason_code == "score_below_minimum"


# --- Records and handoff entries -----------------------------------------------------------------------------


def test_records_keep_estimates_and_assessments_apart() -> None:
    estimate_record = RiskEstimateRecord.from_estimate(risk_estimate(), latency_ms=4)
    assert {"probability", "band"} <= internal_fields(RiskEstimateRecord)
    assessment_record = EligibilityAssessmentRecord.from_assessment(eligibility_assessment())
    assert [(rule.rule_id, rule.rule_version) for rule in assessment_record.rules] == [("ELG.min_credit_score", 1)]
    assert not set(EligibilityAssessmentRecord.model_fields) & {"probability", "band", "interval_low"}
    assert estimate_record.latency_ms == 4
    with pytest.raises(ValidationError, match="low <= probability"):
        estimate_record.evolve(interval_low=Decimal("0.5"))


def test_credit_review_summarizes_for_a_reviewer_with_an_internal_estimate() -> None:
    assessment = eligibility_assessment(outcome="review_required", review_reasons=["borderline_risk_interval"])
    review = CreditReview.from_assessment(
        assessment, estimate=risk_estimate(), extra_reasons=(ReviewReason.CUSTOMER_CONTESTS_RESULT,)
    )
    assert review.review_reasons == (ReviewReason.BORDERLINE_RISK_INTERVAL, ReviewReason.CUSTOMER_CONTESTS_RESULT)
    assert review.risk is not None
    assert review.risk.band is RiskBand.LOW
    assert "risk" in internal_fields(CreditReview)
    assert CreditReview.from_assessment(eligibility_assessment()).risk is None
    with pytest.raises(ValidationError, match="review reason or a missing fact"):
        CreditReview(product_code=assessment.product_code, eligibility_outcome=EligibilityOutcome.REVIEW_REQUIRED)
    with pytest.raises(ValidationError, match="low <= high"):
        review.risk.evolve(interval_low=Decimal("0.9"))
