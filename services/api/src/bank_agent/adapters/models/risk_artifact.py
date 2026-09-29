"""The ``risk_classifier/1`` artifact: plain parameters for the learned risk estimators, evaluated in pure Python.

``bank-ml risk train`` exports logistic regression (``linear`` scorer) or LightGBM (``trees`` scorer) together with
the calibrator chosen on dev (identity, Platt, or isotonic), the uncertainty method chosen on dev (a bootstrap
ensemble of recalibrated members, or binned inductive Venn-Abers), the band cut points read from the policy pack
(``ELG-ALL-2``), and the train range of every feature. The API loads it through ``ModelRegistry`` (digest checked),
never imports an ML library, and never unpickles anything.
"""

import bisect
import math
from collections.abc import Sequence
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from bank_agent.adapters.models.risk_features import FEATURE_NAMES
from bank_agent.adapters.models.tree_ensemble import TreeNode

Finite = Annotated[float, Field(allow_inf_nan=False)]
Probability = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
_WIDTH = len(FEATURE_NAMES)


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp = math.exp(value)
    return exp / (1.0 + exp)


class LinearScorer(_Frozen):
    """Logistic regression on standardized, median-imputed features plus one missing indicator per feature."""

    kind: Literal["linear"]
    impute: tuple[Finite, ...]
    mean: tuple[Finite, ...]
    scale: tuple[Annotated[float, Field(gt=0.0, allow_inf_nan=False)], ...]
    weights: tuple[Finite, ...]
    missing_weights: tuple[Finite, ...]
    intercept: Finite

    @model_validator(mode="after")
    def _shapes(self) -> Self:
        parts = (self.impute, self.mean, self.scale, self.weights, self.missing_weights)
        if any(len(part) != _WIDTH for part in parts):
            raise ValueError("a linear scorer needs one value per feature in every vector")
        return self

    def raw(self, row: Sequence[float]) -> float:
        total = self.intercept
        for i, value in enumerate(row):
            absent = math.isnan(value)
            filled = self.impute[i] if absent else value
            total += self.weights[i] * (filled - self.mean[i]) / self.scale[i]
            total += self.missing_weights[i] if absent else 0.0
        return total


class TreeScorer(_Frozen):
    """A LightGBM binary booster; the raw score is the sum of the leaf values (the log-odds)."""

    kind: Literal["trees"]
    trees: Annotated[tuple[TreeNode, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _features(self) -> Self:
        if any(tree.max_feature() >= _WIDTH for tree in self.trees):
            raise ValueError("a split names a feature outside the feature list")
        return self

    def raw(self, row: Sequence[float]) -> float:
        return sum(tree.evaluate(row) for tree in self.trees)


Scorer = Annotated[LinearScorer | TreeScorer, Field(discriminator="kind")]


class IdentityCalibrator(_Frozen):
    kind: Literal["identity"]

    def probability(self, raw: float) -> float:
        return sigmoid(raw)


class PlattCalibrator(_Frozen):
    kind: Literal["platt"]
    a: Finite
    b: Finite

    def probability(self, raw: float) -> float:
        return sigmoid(self.a * raw + self.b)


class IsotonicCalibrator(_Frozen):
    """A non-decreasing step map from the raw score, linearly interpolated and clipped at both ends."""

    kind: Literal["isotonic"]
    x: Annotated[tuple[Finite, ...], Field(min_length=1)]
    y: Annotated[tuple[Probability, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _monotone(self) -> Self:
        if len(self.x) != len(self.y):
            raise ValueError("isotonic x and y need the same length")
        if any(b <= a for a, b in zip(self.x, self.x[1:], strict=False)):
            raise ValueError("isotonic x must be strictly increasing")
        if any(b < a for a, b in zip(self.y, self.y[1:], strict=False)):
            raise ValueError("isotonic y must be non-decreasing")
        return self

    def probability(self, raw: float) -> float:
        if raw <= self.x[0]:
            return self.y[0]
        if raw >= self.x[-1]:
            return self.y[-1]
        right = bisect.bisect_right(self.x, raw)
        x0, x1, y0, y1 = self.x[right - 1], self.x[right], self.y[right - 1], self.y[right]
        return y0 + (y1 - y0) * (raw - x0) / (x1 - x0)


Calibrator = Annotated[IdentityCalibrator | PlattCalibrator | IsotonicCalibrator, Field(discriminator="kind")]


def quantile(values: Sequence[float], q: float) -> float:
    """Linear-interpolation quantile (numpy's default method) of a non-empty sequence."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


class Member(_Frozen):
    scorer: Scorer
    calibrator: Calibrator

    def probability(self, row: Sequence[float]) -> float:
        return self.calibrator.probability(self.scorer.raw(row))


class BootstrapInterval(_Frozen):
    """Percentiles of the estimates of models refit on bootstrap resamples of train and recalibrated on dev."""

    method: Literal["bootstrap"]
    members: Annotated[tuple[Member, ...], Field(min_length=2)]
    lower: Probability
    upper: Probability

    @model_validator(mode="after")
    def _order(self) -> Self:
        if not self.lower < self.upper:
            raise ValueError("the lower quantile must be below the upper quantile")
        return self

    def bounds(self, row: Sequence[float], raw: float) -> tuple[float, float]:
        estimates = [member.probability(row) for member in self.members]
        return quantile(estimates, self.lower), quantile(estimates, self.upper)


class VennAbersInterval(_Frozen):
    """Binned inductive Venn-Abers: the raw score's bin (edges from train quantiles) gives ``[p0, p1]``."""

    method: Literal["venn_abers"]
    edges: tuple[Finite, ...]
    p0: Annotated[tuple[Probability, ...], Field(min_length=1)]
    p1: Annotated[tuple[Probability, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _shapes(self) -> Self:
        if not len(self.p0) == len(self.p1) == len(self.edges) + 1:
            raise ValueError("one p0 and one p1 per bin (edges plus one)")
        if any(b <= a for a, b in zip(self.edges, self.edges[1:], strict=False)):
            raise ValueError("edges must be strictly increasing")
        if any(low > high for low, high in zip(self.p0, self.p1, strict=True)):
            raise ValueError("p0 must not exceed p1")
        return self

    def bounds(self, row: Sequence[float], raw: float) -> tuple[float, float]:
        position = bisect.bisect_right(self.edges, raw)
        return self.p0[position], self.p1[position]


Interval = Annotated[BootstrapInterval | VennAbersInterval, Field(discriminator="method")]


class RiskClassifierArtifact(_Frozen):
    format: Literal["risk_classifier/1"]
    features: Literal["risk_features@1"]
    feature_names: tuple[str, ...]
    label_definition: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
    scorer: Scorer
    calibrator: Calibrator
    interval: Interval
    cut_medium: Probability
    cut_high: Probability
    ranges: tuple[tuple[Finite, Finite], ...]
    wide_width: Probability

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.feature_names != FEATURE_NAMES:
            raise ValueError("the artifact's feature list is not the shared feature list")
        if not 0.0 < self.cut_medium < self.cut_high < 1.0:
            raise ValueError("band cut points must satisfy 0 < medium < high < 1")
        if len(self.ranges) != _WIDTH or any(low > high for low, high in self.ranges):
            raise ValueError("one (min, max) train range per feature")
        return self

    def probability(self, row: Sequence[float]) -> float:
        return self.calibrator.probability(self.scorer.raw(row))

    def estimate(self, row: Sequence[float]) -> tuple[float, float, float]:
        """``(probability, low, high)`` with the interval widened, if needed, to contain the probability."""
        raw = self.scorer.raw(row)
        probability = self.calibrator.probability(raw)
        low, high = self.interval.bounds(row, raw)
        return probability, min(low, probability), max(high, probability)

    def outside_range(self, row: Sequence[float]) -> bool:
        return any(
            not math.isnan(value) and not low <= value <= high
            for value, (low, high) in zip(row, self.ranges, strict=True)
        )
