"""``risk_estimator:score_band@1``: a deterministic baseline for the ``RiskEstimator`` port.

It is not a trained model. It reads only the credit score from ``CreditRiskFeatures`` and maps it to a band with a
deliberately wide interval, so it can serve the credit workflow until phase 10 registers the learned estimator
behind the same port. The table below is documented in ``docs/workflows/credit-information.md``:

- two transition bands have intervals that straddle the synthetic cut points of ``ELG-ALL-2`` (0.20 and 0.35), so
  the eligibility service asks for human review near a cut instead of trusting a coarse baseline;
- a missing score gives band ``unknown`` with the ``missing_features`` flag and the whole unit interval; the
  eligibility service treats it as no estimate. It never guesses a band.

The estimate is labeled a baseline (``label_definition``), ``calibrated`` is false, and it is internal: never shown to
customers and never sent to a language model. Ids and time come from the injected ports.
"""

from dataclasses import dataclass
from decimal import Decimal

from bank_agent.domain.eligibility import CreditRiskFeatures, RiskBand, RiskEstimate, UncertaintyFlag
from bank_agent.domain.identifiers import IdKind, RiskEstimateId
from bank_agent.domain.intelligence import ModelComponent, ModelRef
from bank_agent.ports.determinism import Clock, IdGenerator

SCORE_BAND_ESTIMATOR = ModelRef(component=ModelComponent.RISK_ESTIMATOR, name="score_band", version="1")
LABEL_DEFINITION = "score_band_baseline_prior"


@dataclass(frozen=True)
class ScoreBand:
    min_score: int
    band: RiskBand
    probability: Decimal
    low: Decimal
    high: Decimal
    flags: tuple[UncertaintyFlag, ...] = ()


def _band(min_score: int, band: RiskBand, probability: str, low: str, high: str, *wide: UncertaintyFlag) -> ScoreBand:
    return ScoreBand(min_score, band, Decimal(probability), Decimal(low), Decimal(high), wide)


WIDE = UncertaintyFlag.WIDE_INTERVAL
SCORE_BANDS: tuple[ScoreBand, ...] = (
    _band(740, RiskBand.LOW, "0.06", "0.02", "0.15"),
    _band(680, RiskBand.LOW, "0.15", "0.08", "0.26", WIDE),
    _band(640, RiskBand.MEDIUM, "0.27", "0.22", "0.33"),
    _band(600, RiskBand.MEDIUM, "0.33", "0.25", "0.42", WIDE),
    _band(300, RiskBand.HIGH, "0.50", "0.38", "0.70", WIDE),
)
"""Ordered by descending minimum score; the first band whose minimum the score reaches applies."""
UNKNOWN = ScoreBand(0, RiskBand.UNKNOWN, Decimal("0.50"), Decimal("0.00"), Decimal("1.00"),
                    (UncertaintyFlag.MISSING_FEATURES,))  # fmt: skip


def band_for(score: int | None) -> ScoreBand:
    """The band of ``score``; ``UNKNOWN`` when it is missing."""
    if score is None:
        return UNKNOWN
    return next(band for band in SCORE_BANDS if score >= band.min_score)


class ScoreBandRiskEstimator:
    """Implements ``RiskEstimator``."""

    model = SCORE_BAND_ESTIMATOR

    def __init__(self, clock: Clock, ids: IdGenerator) -> None:
        self._clock = clock
        self._ids = ids

    def estimate(self, features: CreditRiskFeatures) -> RiskEstimate:
        band = band_for(features.credit_score)
        return RiskEstimate(
            estimate_id=RiskEstimateId(self._ids.new(IdKind.RISK_ESTIMATE)),
            model=SCORE_BAND_ESTIMATOR,
            probability=band.probability,
            interval_low=band.low,
            interval_high=band.high,
            band=band.band,
            flags=band.flags,
            label_definition=LABEL_DEFINITION,
            calibrated=False,
            computed_at=self._clock.now(),
        )
