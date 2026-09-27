"""The score-band risk baseline: its table, the transition bands near the synthetic cut points, and missing scores."""

from decimal import Decimal

import pytest

from bank_agent.adapters.models.score_band_risk import (
    SCORE_BAND_ESTIMATOR,
    SCORE_BANDS,
    ScoreBandRiskEstimator,
    band_for,
)
from bank_agent.domain.credit import CreditProductType
from bank_agent.domain.eligibility import CreditRiskFeatures, RiskBand, UncertaintyFlag
from bank_agent.domain.locale import Country
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.ids import SequentialIdGenerator
from bank_agent_builders import T0

CUT_MEDIUM, CUT_HIGH, MARGIN = Decimal("0.20"), Decimal("0.35"), Decimal("0.01")


def features(score: int | None) -> CreditRiskFeatures:
    return CreditRiskFeatures(
        jurisdiction=Country.MX,
        product_type=CreditProductType.PERSONAL_LOAN,
        requested_term_months=24,
        credit_score=score,
    )


def straddles(low: Decimal, high: Decimal) -> bool:
    return any(low < cut + MARGIN and high > cut - MARGIN for cut in (CUT_MEDIUM, CUT_HIGH))


@pytest.mark.parametrize(
    ("score", "band", "borderline"),
    [(850, RiskBand.LOW, False), (740, RiskBand.LOW, False), (739, RiskBand.LOW, True), (680, RiskBand.LOW, True),
     (679, RiskBand.MEDIUM, False), (640, RiskBand.MEDIUM, False), (639, RiskBand.MEDIUM, True),
     (600, RiskBand.MEDIUM, True), (599, RiskBand.HIGH, False), (300, RiskBand.HIGH, False)],
)  # fmt: skip
def test_scores_map_to_documented_bands_and_transition_bands_straddle_a_cut(
    score: int, band: RiskBand, borderline: bool
) -> None:
    chosen = band_for(score)
    assert chosen.band is band
    assert straddles(chosen.low, chosen.high) is borderline


def test_the_table_is_ordered_and_every_interval_contains_its_probability() -> None:
    minimums = [band.min_score for band in SCORE_BANDS]
    assert minimums == sorted(minimums, reverse=True)
    assert minimums[-1] == 300
    assert all(band.low <= band.probability <= band.high for band in SCORE_BANDS)


def test_a_missing_score_gives_an_unknown_band_with_a_flag_never_a_guessed_band() -> None:
    estimate = ScoreBandRiskEstimator(FixedClock(T0), SequentialIdGenerator()).estimate(features(None))
    assert estimate.band is RiskBand.UNKNOWN
    assert UncertaintyFlag.MISSING_FEATURES in estimate.flags
    assert (estimate.interval_low, estimate.interval_high) == (Decimal("0.00"), Decimal("1.00"))


def test_estimates_are_deterministic_labeled_a_baseline_and_use_the_injected_ports() -> None:
    estimator = ScoreBandRiskEstimator(FixedClock(T0), SequentialIdGenerator())
    first, second = estimator.estimate(features(760)), estimator.estimate(features(760))
    assert first.model == SCORE_BAND_ESTIMATOR
    assert str(first.model) == "risk_estimator:score_band@1"
    assert (first.probability, first.interval_low, first.interval_high, first.band) == (
        second.probability, second.interval_low, second.interval_high, second.band,
    )  # fmt: skip
    assert (first.estimate_id, second.estimate_id) == ("rsk-000001", "rsk-000002")
    assert first.computed_at == T0
    assert first.calibrated is False
    assert first.synthetic_data is True
