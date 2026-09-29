"""A risk estimator that never estimates: served when a learned estimator cannot load and the score-band fallback
is not allowed (``DEGRADATION_RISK_BAND_FALLBACK=false``). Every call raises ``RiskEstimatorUnavailableError``, so the
credit workflow records no estimate (never a default one) and the synthetic eligibility service answers
``review_required``."""

from bank_agent.domain.eligibility import CreditRiskFeatures, RiskEstimate
from bank_agent.domain.errors import RiskEstimatorUnavailableError


class UnavailableRiskEstimator:
    """Implements ``RiskEstimator`` by refusing every estimate."""

    def __init__(self, selection: str) -> None:
        self.selection = selection

    def estimate(self, features: CreditRiskFeatures) -> RiskEstimate:
        raise RiskEstimatorUnavailableError(f"{self.selection} could not load at startup")
