"""Risk metrics with 95% bootstrap intervals.

Every row is one customer, so resampling rows is the customer bootstrap (``cluster_bootstrap`` with singleton
clusters, done directly for speed). ROC AUC uses the rank formula with average ranks for ties; PR AUC is average
precision (scikit-learn's definition); the Brier score, log loss, and expected calibration error (10 equal-width
bins, ``bank_ml.common.metrics``) complete the set. Paired differences resample the same customers for both models.
"""

from collections.abc import Callable
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.metrics import average_precision_score

from bank_ml.common.metrics import BOOTSTRAP_SAMPLES, LEVEL, expected_calibration_error, reliability
from bank_ml.common.seeds import seed_for
from bank_ml.risk.calibration import log_loss

Statistic = Callable[[NDArray[np.int64]], float]
Metric = Callable[[NDArray[np.int64], NDArray[np.float64]], float]


def average_ranks(values: NDArray[np.float64]) -> NDArray[np.float64]:
    """1-based ranks with ties sharing their average rank."""
    _, inverse, counts = np.unique(values, return_inverse=True, return_counts=True)
    upper = np.cumsum(counts)
    return np.asarray((upper - (counts - 1) / 2.0)[inverse], dtype=np.float64)


def roc_auc(y: NDArray[np.int64], p: NDArray[np.float64]) -> float:
    positives = int(y.sum())
    negatives = len(y) - positives
    if positives == 0 or negatives == 0:
        return float("nan")
    ranks = average_ranks(p)
    return float((ranks[y == 1].sum() - positives * (positives + 1) / 2) / (positives * negatives))


def pr_auc(y: NDArray[np.int64], p: NDArray[np.float64]) -> float:
    return float(average_precision_score(y, p)) if 0 < y.sum() < len(y) else float("nan")


def brier(y: NDArray[np.int64], p: NDArray[np.float64]) -> float:
    return float(np.mean((p - y) ** 2)) if len(y) else float("nan")


def ece(y: NDArray[np.int64], p: NDArray[np.float64]) -> float:
    return expected_calibration_error(p, y.astype(bool))


METRICS: dict[str, Metric] = {
    "roc_auc": roc_auc,
    "pr_auc": pr_auc,
    "brier": brier,
    "log_loss": log_loss,
    "ece": ece,
}


def bootstrap(size: int, statistic: Statistic, name: str, samples: int = BOOTSTRAP_SAMPLES) -> dict[str, float]:
    estimate = statistic(np.arange(size, dtype=np.int64))
    if size < 2:
        return {"estimate": estimate, "low": estimate, "high": estimate}
    generator = np.random.default_rng(seed_for("bootstrap", name))
    values = np.array([statistic(generator.integers(0, size, size=size)) for _ in range(samples)])
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return {"estimate": estimate, "low": float("nan"), "high": float("nan")}
    tail = (1.0 - LEVEL) / 2.0
    return {"estimate": estimate, "low": float(np.quantile(values, tail)), "high": float(np.quantile(values, 1 - tail))}


def summary(
    y: NDArray[np.int64], p: NDArray[np.float64], name: str, samples: int = BOOTSTRAP_SAMPLES
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "customers": len(y),
        "positives": int(y.sum()),
        "prevalence": float(y.mean()) if len(y) else float("nan"),
    }
    for key, metric in METRICS.items():
        result[key] = bootstrap(len(y), on_rows(metric, y, p), f"{name}:{key}", samples)
    return result


def on_rows(metric: Metric, y: NDArray[np.int64], p: NDArray[np.float64]) -> Statistic:
    """``metric`` evaluated on the rows a bootstrap sample picks."""

    def statistic(idx: NDArray[np.int64]) -> float:
        return metric(y[idx], p[idx])

    return statistic


def paired_difference(
    y: NDArray[np.int64], candidate: NDArray[np.float64], reference: NDArray[np.float64], metric: str, name: str
) -> dict[str, float]:
    """``metric(candidate) - metric(reference)`` over the same resampled customers."""
    function = METRICS[metric]

    def statistic(idx: NDArray[np.int64]) -> float:
        return function(y[idx], candidate[idx]) - function(y[idx], reference[idx])

    return bootstrap(len(y), statistic, f"{name}:diff:{metric}")


def reliability_table(y: NDArray[np.int64], p: NDArray[np.float64], bins: int = 10) -> list[dict[str, float]]:
    return [
        {
            "lower": b.lower,
            "upper": b.upper,
            "count": b.count,
            "mean_estimate": b.mean_confidence,
            "observed": b.accuracy,
        }
        for b in reliability(p, y.astype(bool), bins)
    ]
