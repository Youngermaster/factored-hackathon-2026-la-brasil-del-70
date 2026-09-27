"""Threshold selection on the dev split: the largest coverage whose risk stays within a target.

The router abstains (asks which workflow) below a confidence threshold; the resolver auto-selects only above a
margin threshold. Both choose the lowest threshold whose error rate among the covered items is at most the target,
which maximizes coverage. When no threshold meets the target, the one with the lowest risk is returned with
``met=False`` and the report says so.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from bank_ml.common.metrics import coverage_risk


@dataclass(frozen=True)
class ThresholdChoice:
    threshold: float
    coverage: float
    risk: float
    target: float
    met: bool


def choose_threshold(scores: NDArray[np.float64], correct: NDArray[np.bool_], target: float) -> ThresholdChoice:
    points = coverage_risk(scores, correct)
    if not points:
        return ThresholdChoice(1.0, 0.0, 0.0, target, met=False)
    meeting = [point for point in points if point[2] <= target]
    if meeting:
        threshold, coverage, risk = max(meeting, key=lambda point: (point[1], -point[0]))
        return ThresholdChoice(threshold, coverage, risk, target, met=True)
    threshold, coverage, risk = min(points, key=lambda point: (point[2], -point[1]))
    return ThresholdChoice(threshold, coverage, risk, target, met=False)


def apply_threshold(scores: NDArray[np.float64], correct: NDArray[np.bool_], threshold: float) -> tuple[float, float]:
    """``(coverage, risk)`` of ``threshold`` on another split."""
    covered = scores >= threshold
    coverage = float(covered.mean()) if len(scores) else 0.0
    risk = float((~correct[covered]).mean()) if covered.any() else 0.0
    return coverage, risk
