"""Evaluation metrics with confidence intervals.

Classification: accuracy, per-class precision, recall, and F1 with support, macro-F1 over the classes present in
the reference labels, and confusion matrices. Calibration: reliability bins and the expected calibration error
(equal-width bins, weighted by count). Selective prediction: the coverage-risk curve. Ranking: top-1 and mean
reciprocal rank. Intervals: a percentile bootstrap that resamples whole clusters (seed groups, customers, or
queries), because items that share a seed or a customer are not independent.
"""

from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from bank_ml.common.seeds import seed_for

BOOTSTRAP_SAMPLES = 1000
LEVEL = 0.95


@dataclass(frozen=True)
class Interval:
    estimate: float
    low: float
    high: float

    def fmt(self, digits: int = 3) -> str:
        return f"{self.estimate:.{digits}f} [{self.low:.{digits}f}, {self.high:.{digits}f}]"


@dataclass(frozen=True)
class ClassScores:
    precision: float
    recall: float
    f1: float
    support: int


@dataclass(frozen=True)
class ReliabilityBin:
    lower: float
    upper: float
    count: int
    mean_confidence: float
    accuracy: float


def encode(values: Sequence[Hashable], labels: Sequence[Hashable]) -> NDArray[np.int64]:
    index = {label: position for position, label in enumerate(labels)}
    return np.array([index.get(value, -1) for value in values], dtype=np.int64)


def confusion(truth: NDArray[np.int64], predicted: NDArray[np.int64], size: int) -> NDArray[np.int64]:
    """``matrix[true][predicted]``; predictions outside the label set (``-1``) are counted in no column."""
    valid = predicted >= 0
    flat = truth[valid] * size + predicted[valid]
    matrix = np.bincount(flat, minlength=size * size).reshape(size, size)
    return matrix.astype(np.int64)


def class_scores(matrix: NDArray[np.int64], truth_counts: NDArray[np.int64]) -> list[ClassScores]:
    scores: list[ClassScores] = []
    predicted_counts = matrix.sum(axis=0)
    for klass in range(matrix.shape[0]):
        hits = int(matrix[klass, klass])
        precision = hits / predicted_counts[klass] if predicted_counts[klass] else 0.0
        recall = hits / truth_counts[klass] if truth_counts[klass] else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        scores.append(ClassScores(float(precision), float(recall), float(f1), int(truth_counts[klass])))
    return scores


def macro_f1(truth: NDArray[np.int64], predicted: NDArray[np.int64], size: int) -> float:
    counts = np.bincount(truth, minlength=size)
    scores = class_scores(confusion(truth, predicted, size), counts)
    present = [score.f1 for score, count in zip(scores, counts, strict=True) if count > 0]
    return float(np.mean(present)) if present else 0.0


def reliability(confidence: NDArray[np.float64], correct: NDArray[np.bool_], bins: int = 10) -> list[ReliabilityBin]:
    edges = np.linspace(0.0, 1.0, bins + 1)
    positions = np.clip(np.digitize(confidence, edges[1:-1], right=True), 0, bins - 1)
    result: list[ReliabilityBin] = []
    for index in range(bins):
        mask = positions == index
        count = int(mask.sum())
        mean_conf = float(confidence[mask].mean()) if count else 0.0
        accuracy = float(correct[mask].mean()) if count else 0.0
        result.append(ReliabilityBin(float(edges[index]), float(edges[index + 1]), count, mean_conf, accuracy))
    return result


def expected_calibration_error(confidence: NDArray[np.float64], correct: NDArray[np.bool_], bins: int = 10) -> float:
    total = len(confidence)
    if total == 0:
        return 0.0
    return float(
        sum(b.count / total * abs(b.accuracy - b.mean_confidence) for b in reliability(confidence, correct, bins))
    )


def coverage_risk(confidence: NDArray[np.float64], correct: NDArray[np.bool_]) -> list[tuple[float, float, float]]:
    """``(threshold, coverage, risk)`` for every distinct confidence, from the highest threshold down."""
    order = np.argsort(-confidence, kind="stable")
    sorted_conf, sorted_correct = confidence[order], correct[order]
    errors = np.cumsum(~sorted_correct)
    points: list[tuple[float, float, float]] = []
    total = len(confidence)
    for position in range(total):
        if position + 1 < total and sorted_conf[position + 1] == sorted_conf[position]:
            continue
        covered = position + 1
        points.append((float(sorted_conf[position]), covered / total, float(errors[position] / covered)))
    return points


def reciprocal_rank(rank: int | None) -> float:
    return 0.0 if rank is None else 1.0 / rank


def cluster_bootstrap(
    clusters: Sequence[Hashable],
    statistic: Callable[[NDArray[np.int64]], float],
    *,
    name: str,
    samples: int = BOOTSTRAP_SAMPLES,
) -> Interval:
    """Percentile interval of ``statistic(item indices)``, resampling whole clusters with replacement."""
    keys = list(dict.fromkeys(clusters))
    members: dict[Hashable, list[int]] = {key: [] for key in keys}
    for position, key in enumerate(clusters):
        members[key].append(position)
    arrays = [np.array(members[key], dtype=np.int64) for key in keys]
    estimate = statistic(np.arange(len(clusters), dtype=np.int64))
    if len(keys) < 2:
        return Interval(estimate, estimate, estimate)
    generator = np.random.default_rng(seed_for("bootstrap", name))
    values = np.empty(samples)
    for sample in range(samples):
        chosen = generator.integers(0, len(arrays), size=len(arrays))
        values[sample] = statistic(np.concatenate([arrays[i] for i in chosen]))
    tail = (1.0 - LEVEL) / 2.0
    return Interval(estimate, float(np.quantile(values, tail)), float(np.quantile(values, 1.0 - tail)))
