"""Properties of the credit path over the real pack and catalog: for any combination of profile gaps and estimator
outcomes, no customer text contains approval wording or an internal figure, and ``indicatively_eligible`` never
exists without a complete profile and an available estimate. The estimator being unavailable never yields a
default estimate and always asks for review."""

from datetime import UTC, date, datetime

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from bank_agent.adapters.models.score_band_risk import ScoreBandRiskEstimator
from bank_agent.application.engine.context import CreditPorts
from bank_agent.application.workflows.credit.assessment import assess, build_features, estimate_risk
from bank_agent.domain.credit import CreditProfile
from bank_agent.domain.eligibility import (
    CreditRiskFeatures,
    EligibilityOutcome,
    EligibilityView,
    ReviewReason,
    RiskBand,
    RiskEstimate,
)
from bank_agent.domain.errors import RiskEstimatorUnavailableError
from bank_agent.domain.identifiers import CreditProductCode, CustomerId
from bank_agent.domain.locale import Country, Language, Locale
from bank_agent.domain.money import Currency, Money
from bank_agent.policy.eligibility import render_eligibility
from bank_agent.policy.lexicon import approval_terms
from bank_agent.ports.eligibility import CreditApplicationFacts
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.ids import SequentialIdGenerator
from bank_agent_workflows import shared_policy

NOW = datetime(2026, 6, 18, 15, 0, tzinfo=UTC)


class Unavailable:
    def estimate(self, features: CreditRiskFeatures) -> RiskEstimate:
        raise RiskEstimatorUnavailableError("fixture")


def ports(available: bool) -> CreditPorts:
    policy, _ = shared_policy()
    estimator = ScoreBandRiskEstimator(FixedClock(NOW), SequentialIdGenerator()) if available else Unavailable()
    return CreditPorts(catalog=policy.catalog, eligibility=policy.eligibility, risk_estimator=estimator)


profiles = st.builds(
    lambda score, income, tenure, dpd: CreditProfile(
        customer_id=CustomerId("CLI-FIXPROP001"),
        credit_score=score,
        estimated_monthly_income=Money.of(str(income), Currency.MXN) if income is not None else None,
        tenure_months=tenure,
        max_days_past_due=dpd,
        as_of=date(2026, 6, 17),
    ),
    st.one_of(st.none(), st.integers(300, 850)),
    st.one_of(st.none(), st.integers(1000, 200000)),
    st.one_of(st.none(), st.integers(0, 120)),
    st.one_of(st.none(), st.sampled_from([0, 0, 15, 60])),
)
requests = st.tuples(
    st.sampled_from(["MX-CC-CLASSIC", "MX-PL-STANDARD", "MX-MG-FIXED"]),
    st.integers(5000, 350000),
    st.integers(6, 60),
)


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(profile=st.one_of(st.none(), profiles), request=requests, available=st.booleans(),
       language=st.sampled_from([Language.ES, Language.PT]))  # fmt: skip
def test_no_approval_wording_and_no_indicative_result_without_complete_facts(
    profile: CreditProfile | None, request: tuple[str, int, int], available: bool, language: Language
) -> None:
    code, amount, term = request
    credit = ports(available)
    product = credit.catalog.get(CreditProductCode(code))
    assert product is not None
    term = min(max(term, product.min_term_months), product.max_term_months)
    application = CreditApplicationFacts(
        requested_amount=Money.of(str(amount), Currency.MXN), requested_term_months=term, purpose="general_purpose"
    )
    estimated = estimate_risk(credit, build_features(Country.MX, product, application, profile))
    if not available:
        assert (estimated.estimate, estimated.record) == (None, None)
    assessment = assess(credit, product, profile, application, estimated.estimate, now=NOW)
    complete = profile is not None and None not in (
        profile.credit_score,
        profile.estimated_monthly_income,
        profile.tenure_months,
        profile.max_days_past_due,
    )
    usable = estimated.estimate is not None and estimated.estimate.band is not RiskBand.UNKNOWN
    if assessment.outcome is EligibilityOutcome.INDICATIVELY_ELIGIBLE:
        assert complete
        assert usable
    if not available and assessment.outcome is not EligibilityOutcome.INSUFFICIENT_DATA:
        assert assessment.outcome is EligibilityOutcome.REVIEW_REQUIRED or not product.self_service_eligibility
        if product.self_service_eligibility:
            assert ReviewReason.RISK_ESTIMATE_UNAVAILABLE in assessment.review_reasons
    policy, _ = shared_policy()
    locale = Locale.ES_MX if language is Language.ES else Locale.PT_BR
    text = render_eligibility(policy.pack, EligibilityView.from_assessment(assessment), language, locale).text
    assert approval_terms(text) == ()
    if profile is not None and profile.credit_score is not None:
        assert f" {profile.credit_score} " not in f" {text} "
    if estimated.estimate is not None:
        assert str(estimated.estimate.probability) not in text
        assert str((estimated.estimate.probability * 100).normalize()) + " %" not in text
