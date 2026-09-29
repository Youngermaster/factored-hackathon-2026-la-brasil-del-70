"""Contract suites for the credit model ports: the risk estimator and the eligibility policy.

The eligibility suite runs against the fake and the synthetic eligibility service (phase 06, on the real pack);
the estimator suite runs against the fake, the score-band baseline, and the learned ``logreg`` and ``lgbm`` estimators
(from hand-written fixture artifacts in a temporary registry).
"""

import tempfile
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from bank_agent.adapters.models.learned_risk import LearnedRiskEstimator
from bank_agent.adapters.models.score_band_risk import ScoreBandRiskEstimator
from bank_agent.adapters.policy.filesystem import FilesystemPolicyRepository
from bank_agent.bootstrap.settings import DEFAULT_POLICY_DIR
from bank_agent.domain.credit import CreditProductType, CreditProfile
from bank_agent.domain.eligibility import (
    CreditRiskFeatures,
    EligibilityOutcome,
    ReviewReason,
    RiskBand,
    UncertaintyFlag,
)
from bank_agent.domain.identifiers import CreditProductCode, CustomerId
from bank_agent.domain.intelligence import ModelComponent
from bank_agent.domain.locale import Country
from bank_agent.domain.money import Currency, Money
from bank_agent.policy.eligibility import SyntheticEligibilityService
from bank_agent.ports.eligibility import CreditApplicationFacts, EligibilityPolicy, EligibilityRequest
from bank_agent.ports.models import RiskEstimator
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.credit import FakeEligibilityPolicy, FakeRiskEstimator
from bank_agent.testing.ids import SequentialIdGenerator
from bank_agent_builders import CUSTOMER_A, T0, risk_estimate
from bank_agent_credit import catalog_products
from bank_agent_models import RISK_LGBM_ARTIFACT, RISK_LOGREG_ARTIFACT, publish


def _learned(name: str, artifact: dict[str, Any]) -> Callable[[], RiskEstimator]:
    def factory() -> RiskEstimator:
        root = Path(tempfile.mkdtemp(prefix="model-registry-"))
        return LearnedRiskEstimator.load(publish(root, name, artifact), FixedClock(T0), SequentialIdGenerator())

    return factory


RISK_ESTIMATORS = [
    pytest.param(lambda: FakeRiskEstimator(FixedClock(T0), SequentialIdGenerator()), marks=pytest.mark.unit, id="fake"),
    pytest.param(
        lambda: ScoreBandRiskEstimator(FixedClock(T0), SequentialIdGenerator()), marks=pytest.mark.unit, id="score_band"
    ),
    pytest.param(_learned("risk_estimator:logreg", RISK_LOGREG_ARTIFACT), marks=pytest.mark.unit, id="logreg"),
    pytest.param(_learned("risk_estimator:lgbm", RISK_LGBM_ARTIFACT), marks=pytest.mark.unit, id="lgbm"),
]


def _synthetic_service() -> EligibilityPolicy:
    pack = FilesystemPolicyRepository.from_directory(DEFAULT_POLICY_DIR).pack
    return SyntheticEligibilityService(pack, FixedClock(T0), SequentialIdGenerator())


ELIGIBILITY_POLICIES = [
    pytest.param(
        lambda: FakeEligibilityPolicy(FixedClock(T0), SequentialIdGenerator()), marks=pytest.mark.unit, id="fake"
    ),
    pytest.param(_synthetic_service, marks=pytest.mark.integration, id="synthetic"),
]

FEATURES = CreditRiskFeatures(
    jurisdiction=Country.MX,
    product_type=CreditProductType.PERSONAL_LOAN,
    requested_term_months=24,
    credit_score=712,
    monthly_income_usd=Decimal("1750.00"),
    tenure_months=52,
    credit_product_count=1,
    max_days_past_due=0,
    utilization=Decimal("0.42"),
    requested_amount_to_income=Decimal("1.25"),
)


@pytest.mark.parametrize("factory", RISK_ESTIMATORS)
class TestRiskEstimatorContract:
    def test_returns_a_versioned_synthetic_estimate_within_bounds(self, factory: Callable[[], RiskEstimator]) -> None:
        estimate = factory().estimate(FEATURES)
        assert estimate.model.component is ModelComponent.RISK_ESTIMATOR
        assert estimate.model.version
        assert Decimal(0) <= estimate.interval_low <= estimate.probability <= estimate.interval_high <= Decimal(1)
        assert estimate.synthetic_data is True
        assert estimate.label_definition

    def test_numbers_are_deterministic_for_the_same_features(self, factory: Callable[[], RiskEstimator]) -> None:
        estimator = factory()
        first, second = estimator.estimate(FEATURES), estimator.estimate(FEATURES)
        numbers = ("probability", "interval_low", "interval_high", "band", "flags", "model")
        assert all(getattr(first, name) == getattr(second, name) for name in numbers)
        assert first.estimate_id != second.estimate_id

    def test_accepts_features_with_missing_values(self, factory: Callable[[], RiskEstimator]) -> None:
        sparse = CreditRiskFeatures(
            jurisdiction=Country.CO, product_type=CreditProductType.CREDIT_CARD, requested_term_months=12
        )
        estimate = factory().estimate(sparse)
        assert estimate.band in RiskBand


def _profile(**overrides: object) -> CreditProfile:
    fields: dict[str, object] = {
        "customer_id": CustomerId(CUSTOMER_A),
        "credit_score": 712,
        "estimated_monthly_income": Money.of("32000.00", Currency.MXN),
        "tenure_months": 52,
        "max_days_past_due": 0,
        "as_of": date(2026, 5, 31),
    }
    return CreditProfile.model_validate({**fields, **overrides})


def _request(code: str = "MX-PL-FIXTURE", **overrides: object) -> EligibilityRequest:
    product = next(p for p in catalog_products() if p.product_code == CreditProductCode(code))
    fields: dict[str, object] = {
        "product": product,
        "profile": _profile(),
        "application": CreditApplicationFacts(
            requested_amount=Money.of("40000.00", product.currency), requested_term_months=24, purpose="general_purpose"
        ),
        "risk_estimate": risk_estimate(),
        "jurisdiction": product.jurisdiction,
        "as_of": T0,
    }
    return EligibilityRequest.model_validate({**fields, **overrides})


@pytest.mark.parametrize("factory", ELIGIBILITY_POLICIES)
class TestEligibilityPolicyContract:
    def test_identifies_itself_as_synthetic_and_uses_elg_rules(self, factory: Callable[[], EligibilityPolicy]) -> None:
        assessment = factory().assess(_request())
        assert assessment.synthetic is True
        assert str(assessment.service).startswith("eligibility:")
        assert assessment.product_code == "MX-PL-FIXTURE"
        assert assessment.rule_results
        assert all(result.rule_id.startswith("ELG.") for result in assessment.rule_results)
        assert assessment.risk_estimate_ref is not None

    def test_is_deterministic_for_the_same_request(self, factory: Callable[[], EligibilityPolicy]) -> None:
        policy = factory()
        first, second = policy.assess(_request()), policy.assess(_request())
        same = ("outcome", "rule_results", "review_reasons", "missing_facts", "service", "policy_pack_version")
        assert all(getattr(first, name) == getattr(second, name) for name in same)

    def test_a_missing_estimate_requires_review(self, factory: Callable[[], EligibilityPolicy]) -> None:
        assessment = factory().assess(_request(risk_estimate=None))
        assert assessment.outcome is EligibilityOutcome.REVIEW_REQUIRED
        assert ReviewReason.RISK_ESTIMATE_UNAVAILABLE in assessment.review_reasons
        assert assessment.risk_estimate_ref is None

    def test_an_unknown_band_requires_review(self, factory: Callable[[], EligibilityPolicy]) -> None:
        unknown = risk_estimate(band=RiskBand.UNKNOWN, flags=[UncertaintyFlag.OUT_OF_DISTRIBUTION])
        assessment = factory().assess(_request(risk_estimate=unknown))
        assert assessment.outcome is EligibilityOutcome.REVIEW_REQUIRED

    @pytest.mark.parametrize(
        "profile",
        [None, _profile(estimated_monthly_income=None), _profile(credit_score=None)],
        ids=["no_profile", "no_income", "no_score"],
    )
    def test_missing_facts_never_give_an_indicative_yes(
        self, factory: Callable[[], EligibilityPolicy], profile: CreditProfile | None
    ) -> None:
        assessment = factory().assess(_request(profile=profile))
        assert assessment.outcome in {EligibilityOutcome.INSUFFICIENT_DATA, EligibilityOutcome.REVIEW_REQUIRED}
        assert assessment.missing_facts

    def test_a_product_without_self_service_eligibility_requires_review(
        self, factory: Callable[[], EligibilityPolicy]
    ) -> None:
        assessment = factory().assess(_request("CO-MG-FIXTURE", profile=None, risk_estimate=None))
        assert assessment.outcome is EligibilityOutcome.REVIEW_REQUIRED
        assert ReviewReason.PRODUCT_REQUIRES_HUMAN_ASSESSMENT in assessment.review_reasons
