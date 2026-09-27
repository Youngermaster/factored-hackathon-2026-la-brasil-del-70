"""``risk_estimator:logreg`` and ``risk_estimator:lgbm``: learned snapshot risk estimates from a ``risk_classifier/1``
artifact (``risk_artifact.py``), loaded through ``ModelRegistry`` by version or alias.

The estimate is a calibrated probability of the documented label (``label_definition``, for example
``snapshot_dpd30_any_credit_product``: any open credit product 30 or more days past due at the one snapshot the data
has), with an interval and a band from the policy's cut points. It is cross-sectional, trained on synthetic organizer
data, and never a decision; it is internal, never shown to customers and never sent to a language model.

Flags: ``missing_features`` when a model feature is absent (the model was trained with missing values, so the band
stands); ``out_of_distribution`` when a present feature lies outside the train range, which makes the band
``unknown`` so the eligibility service asks for review instead of trusting an extrapolation (a first-time applicant
with no credit product is outside the training population); ``wide_interval`` above the artifact's width. A failure
while computing raises ``RiskEstimatorUnavailableError``; the estimator never returns a default estimate.
"""

from decimal import Decimal

from bank_agent.adapters.models.registry import read_verified
from bank_agent.adapters.models.risk_artifact import RiskClassifierArtifact
from bank_agent.adapters.models.risk_features import FEATURES_ID, from_features, missing
from bank_agent.domain.eligibility import CreditRiskFeatures, RiskBand, RiskEstimate, UncertaintyFlag
from bank_agent.domain.errors import ModelArtifactIntegrityError, RiskEstimatorUnavailableError
from bank_agent.domain.identifiers import IdKind, RiskEstimateId
from bank_agent.domain.intelligence import ModelComponent, ModelRef, ResolvedArtifact
from bank_agent.ports.determinism import Clock, IdGenerator

PLACES = Decimal("0.0001")


def band_for(probability: float, cut_medium: float, cut_high: float) -> RiskBand:
    """Low below the medium cut, medium below the high cut, high from the high cut up (the ``ELG-ALL-2`` cuts)."""
    if probability < cut_medium:
        return RiskBand.LOW
    return RiskBand.MEDIUM if probability < cut_high else RiskBand.HIGH


def _decimal(value: float) -> Decimal:
    return Decimal(repr(min(1.0, max(0.0, value)))).quantize(PLACES)


class LearnedRiskEstimator:
    """Implements ``RiskEstimator`` from a ``risk_classifier/1`` artifact."""

    def __init__(self, artifact: RiskClassifierArtifact, model: ModelRef, clock: Clock, ids: IdGenerator) -> None:
        if artifact.features != FEATURES_ID:
            raise ModelArtifactIntegrityError(f"artifact features {artifact.features} are not {FEATURES_ID}")
        if model.component is not ModelComponent.RISK_ESTIMATOR:
            raise ModelArtifactIntegrityError(f"{model} is not a risk_estimator model")
        self._artifact = artifact
        self._clock = clock
        self._ids = ids
        self.model = model

    @classmethod
    def load(cls, resolved: ResolvedArtifact, clock: Clock, ids: IdGenerator) -> "LearnedRiskEstimator":
        try:
            artifact = RiskClassifierArtifact.model_validate(read_verified(resolved))
        except ValueError as error:
            raise ModelArtifactIntegrityError(f"artifact {resolved.ref} is not a valid risk classifier") from error
        return cls(artifact, resolved.ref, clock, ids)

    @property
    def artifact(self) -> RiskClassifierArtifact:
        return self._artifact

    def estimate(self, features: CreditRiskFeatures) -> RiskEstimate:
        artifact = self._artifact
        row = from_features(features)
        try:
            probability, low, high = artifact.estimate(row)
        except (ValueError, ArithmeticError, IndexError) as error:
            raise RiskEstimatorUnavailableError(f"{self.model} could not score the features") from error
        flags: list[UncertaintyFlag] = []
        if missing(row):
            flags.append(UncertaintyFlag.MISSING_FEATURES)
        outside = artifact.outside_range(row)
        if outside:
            flags.append(UncertaintyFlag.OUT_OF_DISTRIBUTION)
        if high - low > artifact.wide_width:
            flags.append(UncertaintyFlag.WIDE_INTERVAL)
        rounded = _decimal(probability)
        band = RiskBand.UNKNOWN if outside else band_for(float(rounded), artifact.cut_medium, artifact.cut_high)
        return RiskEstimate(
            estimate_id=RiskEstimateId(self._ids.new(IdKind.RISK_ESTIMATE)),
            model=self.model,
            probability=rounded,
            interval_low=_decimal(low),
            interval_high=_decimal(high),
            band=band,
            flags=tuple(flags),
            label_definition=artifact.label_definition,
            calibrated=True,
            computed_at=self._clock.now(),
        )
