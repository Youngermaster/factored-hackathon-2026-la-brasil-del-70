from decimal import Decimal

import pytest

from bank_agent.domain.credit import CreditProductType
from bank_agent.domain.eligibility import CreditRiskFeatures, EligibilityOutcome, ReviewReason, RiskBand
from bank_agent.domain.errors import RiskEstimatorUnavailableError
from bank_agent.domain.locale import Country
from bank_agent.domain.money import Money
from bank_agent.ports.eligibility import CreditApplicationFacts, EligibilityRequest
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.credit import FakeEligibilityPolicy, FakeRiskEstimator, ScriptedRisk, feature_digest
from bank_agent.testing.ids import SequentialIdGenerator
from bank_agent_builders import T0, risk_estimate
from bank_agent_credit import catalog_products, credit_profiles

FEATURES = CreditRiskFeatures(
    jurisdiction=Country.MX, product_type=CreditProductType.CREDIT_CARD, requested_term_months=12, credit_score=640
)
HIGH = ScriptedRisk(
    probability=Decimal("0.41"), interval_low=Decimal("0.30"), interval_high=Decimal("0.55"), band=RiskBand.HIGH
)


def estimator(**kwargs: object) -> FakeRiskEstimator:
    return FakeRiskEstimator(FixedClock(T0), SequentialIdGenerator(), **kwargs)  # type: ignore[arg-type]


def test_scripts_estimates_by_feature_digest_with_a_default() -> None:
    fake = estimator()
    assert fake.estimate(FEATURES).band is RiskBand.LOW
    fake.set(FEATURES, HIGH)
    scripted = fake.estimate(FEATURES)
    assert (scripted.band, scripted.probability) == (RiskBand.HIGH, Decimal("0.41"))
    assert scripted.estimate_id == "rsk-000002"
    assert scripted.computed_at == T0
    assert len(fake.calls) == 2


def test_scripts_given_at_construction_are_used() -> None:
    fake = estimator(scripts={feature_digest(FEATURES): HIGH})
    assert fake.estimate(FEATURES).band is RiskBand.HIGH


def test_the_digest_ignores_nothing_but_is_stable() -> None:
    assert feature_digest(FEATURES) == feature_digest(FEATURES.evolve())
    assert feature_digest(FEATURES) != feature_digest(FEATURES.evolve(credit_score=641))


def test_an_unavailable_estimator_raises_instead_of_guessing() -> None:
    fake = estimator(unavailable=True)
    with pytest.raises(RiskEstimatorUnavailableError):
        fake.estimate(FEATURES)
    assert fake.calls == [FEATURES]


def _request(code: str) -> EligibilityRequest:
    product = next(p for p in catalog_products() if p.product_code == code)
    return EligibilityRequest(
        product=product,
        profile=credit_profiles()[0],
        application=CreditApplicationFacts(
            requested_amount=Money.of("40000.00", product.currency), requested_term_months=24, purpose="general_purpose"
        ),
        risk_estimate=risk_estimate(),
        jurisdiction=product.jurisdiction,
        as_of=T0,
    )


def test_eligibility_outcomes_are_scripted_per_product() -> None:
    policy = FakeEligibilityPolicy(
        FixedClock(T0),
        SequentialIdGenerator(),
        outcomes={
            "MX-CC-FIXTURE": EligibilityOutcome.NOT_ELIGIBLE,
            "MX-PL-FIXTURE": EligibilityOutcome.REVIEW_REQUIRED,
        },
    )
    ineligible = policy.assess(_request("MX-CC-FIXTURE"))
    assert ineligible.outcome is EligibilityOutcome.NOT_ELIGIBLE
    assert ineligible.rule_results[0].clause_refs
    review = policy.assess(_request("MX-PL-FIXTURE"))
    assert review.review_reasons == (ReviewReason.BORDERLINE_RISK_INTERVAL,)
    assert policy.assess(_request("AR-PL-FIXTURE")).outcome is EligibilityOutcome.INDICATIVELY_ELIGIBLE
    assert len(policy.calls) == 3


def test_missing_facts_are_named_with_review_reasons() -> None:
    policy = FakeEligibilityPolicy(FixedClock(T0), SequentialIdGenerator())
    request = _request("MX-PL-FIXTURE").evolve(profile=credit_profiles()[1].evolve(customer_id="CUS-A-0001"))
    assessment = policy.assess(request)
    assert assessment.outcome is EligibilityOutcome.INSUFFICIENT_DATA
    assert assessment.missing_facts == ("estimated_monthly_income",)
    assert assessment.review_reasons == (ReviewReason.MISSING_INCOME,)
    no_profile = policy.assess(_request("MX-PL-FIXTURE").evolve(profile=None))
    assert no_profile.missing_facts == ("credit_profile",)


def test_insufficient_data_cannot_be_scripted() -> None:
    with pytest.raises(ValueError, match="missing facts"):
        FakeEligibilityPolicy(
            FixedClock(T0), SequentialIdGenerator(), outcomes={"MX-CC-FIXTURE": EligibilityOutcome.INSUFFICIENT_DATA}
        )
