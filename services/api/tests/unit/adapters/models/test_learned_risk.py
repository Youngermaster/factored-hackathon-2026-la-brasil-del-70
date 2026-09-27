"""The learned risk estimators over fixture artifacts: scoring, calibration, intervals, bands, flags, and loading."""

import math
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from bank_agent.adapters.models.learned_risk import LearnedRiskEstimator, band_for
from bank_agent.adapters.models.risk_artifact import (
    IsotonicCalibrator,
    RiskClassifierArtifact,
    VennAbersInterval,
    quantile,
    sigmoid,
)
from bank_agent.adapters.models.risk_features import FEATURE_NAMES, from_profile, missing, vector
from bank_agent.domain.credit import CreditProductType, CreditProfile
from bank_agent.domain.eligibility import CreditRiskFeatures, RiskBand, UncertaintyFlag
from bank_agent.domain.errors import ModelArtifactIntegrityError, RiskEstimatorUnavailableError
from bank_agent.domain.identifiers import CustomerId
from bank_agent.domain.intelligence import ModelComponent, ModelRef
from bank_agent.domain.locale import Country
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.ids import SequentialIdGenerator
from bank_agent_builders import CUSTOMER_A, T0
from bank_agent_models import RISK_LGBM_ARTIFACT, RISK_LOGREG_ARTIFACT, publish


def features(**values: Any) -> CreditRiskFeatures:
    base: dict[str, Any] = {
        "jurisdiction": Country.MX,
        "product_type": CreditProductType.PERSONAL_LOAN,
        "requested_term_months": 24,
        "credit_score": 712,
        "tenure_months": 52,
        "credit_product_count": 1,
        "utilization": Decimal("0.42"),
        "max_days_past_due": 0,
    }
    return CreditRiskFeatures.model_validate({**base, **values})


def estimator(artifact: dict[str, Any], tmp_path: Path, name: str = "risk_estimator:lgbm") -> LearnedRiskEstimator:
    return LearnedRiskEstimator.load(publish(tmp_path, name, artifact), FixedClock(T0), SequentialIdGenerator())


def test_the_feature_vector_is_shared_and_never_reads_days_past_due() -> None:
    assert FEATURE_NAMES == ("credit_score", "tenure_months", "credit_product_count", "utilization")
    profile = CreditProfile(customer_id=CustomerId(CUSTOMER_A), credit_score=700, tenure_months=10,
                            credit_product_count=2, max_days_past_due=90, as_of=T0.date())  # fmt: skip
    row = from_profile(profile)
    assert row[:3] == [700.0, 10.0, 2.0]
    assert math.isnan(row[3])
    assert missing(row) == ("utilization",)
    assert vector(1, 2, 3, Decimal("0.5")) == [1.0, 2.0, 3.0, 0.5]


def test_lgbm_estimate_uses_the_calibrated_tree_score_and_the_venn_abers_bin(tmp_path: Path) -> None:
    learned = estimator(RISK_LGBM_ARTIFACT, tmp_path)
    one = learned.estimate(features(credit_product_count=1))
    assert (one.probability, one.interval_low, one.interval_high) == (Decimal("0.12"), Decimal("0.11"), Decimal("0.13"))
    assert (one.band, one.flags, one.calibrated) == (RiskBand.LOW, (), True)
    assert one.label_definition == "snapshot_dpd30_any_credit_product"
    assert (one.model.component, one.model.name) == (ModelComponent.RISK_ESTIMATOR, "lgbm")
    three = learned.estimate(features(credit_product_count=3))
    assert (three.probability, three.band) == (Decimal("0.38"), RiskBand.HIGH)
    assert three.interval_low <= three.probability <= three.interval_high


def test_logreg_estimate_takes_bootstrap_percentiles_widened_to_the_probability(tmp_path: Path) -> None:
    learned = estimator(RISK_LOGREG_ARTIFACT, tmp_path, "risk_estimator:logreg")
    estimate = learned.estimate(features())
    assert estimate.interval_low <= estimate.probability <= estimate.interval_high
    assert estimate.band is RiskBand.LOW
    assert learned.estimate(features()).probability == estimate.probability


def test_missing_features_keep_a_band_and_raise_the_flag(tmp_path: Path) -> None:
    estimate = estimator(RISK_LGBM_ARTIFACT, tmp_path).estimate(features(utilization=None, credit_score=None))
    assert UncertaintyFlag.MISSING_FEATURES in estimate.flags
    assert estimate.band is not RiskBand.UNKNOWN


def test_a_first_time_applicant_is_out_of_distribution_and_gets_an_unknown_band(tmp_path: Path) -> None:
    estimate = estimator(RISK_LGBM_ARTIFACT, tmp_path).estimate(features(credit_product_count=0))
    assert estimate.band is RiskBand.UNKNOWN
    assert UncertaintyFlag.OUT_OF_DISTRIBUTION in estimate.flags


def test_a_wide_interval_is_flagged(tmp_path: Path) -> None:
    wide = {**RISK_LGBM_ARTIFACT, "interval": {**RISK_LGBM_ARTIFACT["interval"], "p0": [0.0, 0.0, 0.0]}}
    estimate = estimator(wide, tmp_path).estimate(features(credit_product_count=3))
    assert UncertaintyFlag.WIDE_INTERVAL in estimate.flags


@pytest.mark.parametrize(
    ("probability", "band"),
    [(0.1999, RiskBand.LOW), (0.2, RiskBand.MEDIUM), (0.3499, RiskBand.MEDIUM), (0.35, RiskBand.HIGH)],
)
def test_bands_follow_the_policy_cut_points(probability: float, band: RiskBand) -> None:
    assert band_for(probability, 0.20, 0.35) is band


def test_a_scoring_failure_is_unavailable_never_a_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    learned = estimator(RISK_LGBM_ARTIFACT, tmp_path)

    def broken(self: RiskClassifierArtifact, row: list[float]) -> tuple[float, float, float]:
        raise ArithmeticError("overflow")

    monkeypatch.setattr(RiskClassifierArtifact, "estimate", broken)
    with pytest.raises(RiskEstimatorUnavailableError):
        learned.estimate(features())


def test_a_malformed_artifact_or_wrong_component_is_refused(tmp_path: Path) -> None:
    bad = {**RISK_LGBM_ARTIFACT, "cut_medium": 0.5, "cut_high": 0.4}
    with pytest.raises(ModelArtifactIntegrityError):
        estimator(bad, tmp_path)
    artifact = RiskClassifierArtifact.model_validate(RISK_LGBM_ARTIFACT)
    router = ModelRef(component=ModelComponent.ROUTER, name="tfidf", version="1")
    with pytest.raises(ModelArtifactIntegrityError):
        LearnedRiskEstimator(artifact, router, FixedClock(T0), SequentialIdGenerator())


BAD_TREE = {"feature": 9, "threshold": 0.0, "left": {"value": 0.0}, "right": {"value": 1.0}}


@pytest.mark.parametrize(
    "change",
    [
        {"feature_names": ["credit_score"]},
        {"ranges": [[0.0, 1.0]]},
        {"scorer": {**RISK_LOGREG_ARTIFACT["scorer"], "weights": [1.0]}},
        {"scorer": {"kind": "trees", "trees": [BAD_TREE]}},
        {"interval": {"method": "venn_abers", "edges": [0.0], "p0": [0.1], "p1": [0.2]}},
        {"interval": {"method": "venn_abers", "edges": [1.0, 0.0], "p0": [0.1] * 3, "p1": [0.2] * 3}},
        {"interval": {"method": "venn_abers", "edges": [], "p0": [0.3], "p1": [0.2]}},
        {"interval": {**RISK_LOGREG_ARTIFACT["interval"], "lower": 0.9, "upper": 0.1}},
        {"calibrator": {"kind": "isotonic", "x": [0.0, 0.0], "y": [0.1, 0.2]}},
        {"calibrator": {"kind": "isotonic", "x": [0.0, 1.0], "y": [0.3, 0.2]}},
        {"calibrator": {"kind": "isotonic", "x": [0.0, 1.0], "y": [0.3]}},
    ],
)
def test_the_artifact_schema_refuses_inconsistent_parameters(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        RiskClassifierArtifact.model_validate({**RISK_LOGREG_ARTIFACT, **change})


def test_math_helpers() -> None:
    assert (sigmoid(0.0), sigmoid(-800.0), sigmoid(800.0)) == (0.5, 0.0, 1.0)
    assert (quantile([3.0, 1.0, 2.0], 0.5), quantile([1.0, 2.0], 0.25), quantile([4.0], 0.9)) == (2.0, 1.25, 4.0)
    iso = IsotonicCalibrator(kind="isotonic", x=(0.0, 1.0), y=(0.1, 0.3))
    assert (iso.probability(-1.0), iso.probability(2.0)) == (0.1, 0.3)
    assert iso.probability(0.5) == pytest.approx(0.2)
    venn = VennAbersInterval(method="venn_abers", edges=(0.0,), p0=(0.1, 0.2), p1=(0.15, 0.3))
    assert (venn.bounds([], -1.0), venn.bounds([], 0.0)) == ((0.1, 0.15), (0.2, 0.3))
