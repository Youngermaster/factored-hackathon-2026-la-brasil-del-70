"""Uncertainty intervals for the risk estimate, and the dev choice between two methods.

- **Bootstrap ensemble.** ``MEMBERS`` models refit on customer bootstraps of train (fixed hyperparameters), each
  recalibrated with the chosen calibrator on a bootstrap of the dev calibration half, so the interval reflects both
  model and calibration variability. The interval is the 2.5% and 97.5% percentiles of the member estimates.
- **Inductive Venn-Abers** (binned). Split conformal gives label sets for a binary outcome, not a probability
  interval; Venn-Abers is the conformal-family predictor that outputs one. Raw scores are binned on quantile edges
  of the train scores (fixed before calibration, so validity holds for the binned score); for each bin, isotonic
  regression over the dev calibration counts with the query added once as a negative and once as a positive gives
  ``p0`` and ``p1``.

Choice (pre-registered in ``docs/plans/phase-10b.md``): on the dev selection half, sort by the point estimate into
ten equal-count groups; a group is covered when its mean interval intersects the 95% Wilson interval of its observed
rate. The method with item-weighted group coverage of at least ``COVERAGE_TARGET`` and the smaller mean width wins;
if neither reaches it, the higher coverage wins.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from bank_ml.common.seeds import seed_for

MEMBERS = 20
LOWER, UPPER = 0.025, 0.975
VENN_BINS = 50
GROUPS = 10
COVERAGE_TARGET = 0.9
Z = 1.959963984540054


def pava(values: NDArray[np.float64], weights: NDArray[np.float64]) -> NDArray[np.float64]:
    """Weighted isotonic (non-decreasing) regression by pool-adjacent-violators, in the given order."""
    blocks: list[list[float]] = []  # [mean, weight, count]
    for value, weight in zip(values.tolist(), weights.tolist(), strict=True):
        blocks.append([value, weight, 1.0])
        while len(blocks) > 1 and blocks[-2][0] > blocks[-1][0]:
            last = blocks.pop()
            head = blocks[-1]
            total = head[1] + last[1]
            head[0] = (head[0] * head[1] + last[0] * last[1]) / total
            head[1], head[2] = total, head[2] + last[2]
    return np.concatenate([np.full(int(count), mean) for mean, _, count in blocks])


def venn_edges(raw_train: NDArray[np.float64], bins: int = VENN_BINS) -> NDArray[np.float64]:
    """Quantile edges moved to the midpoint between the distinct train scores around them, so no score (tree
    ensembles give few distinct values) sits on an edge where float summation order could flip its bin."""
    distinct = np.unique(raw_train)
    positions = np.searchsorted(distinct, np.quantile(raw_train, np.linspace(0.0, 1.0, bins + 1)[1:-1]), side="right")
    inner = positions[(positions > 0) & (positions < len(distinct))]
    return np.unique((distinct[inner - 1] + distinct[inner]) / 2.0)


def venn_abers(edges: NDArray[np.float64], raw: NDArray[np.float64], y: NDArray[np.int64]) -> dict[str, Any]:
    """The ``venn_abers`` interval block from dev calibration raw scores and labels."""
    position = np.searchsorted(edges, raw, side="right")
    size = len(edges) + 1
    counts = np.bincount(position, minlength=size).astype(np.float64)
    positives = np.bincount(position, weights=y.astype(np.float64), minlength=size)
    p0, p1 = [], []
    for query in range(size):
        pair = []
        for label in (0.0, 1.0):
            weights, sums = counts.copy(), positives.copy()
            weights[query] += 1.0
            sums[query] += label
            present = np.flatnonzero(weights > 0)
            fitted = pava(sums[present] / weights[present], weights[present])
            pair.append(float(fitted[int(np.searchsorted(present, query))]))
        p0.append(pair[0])
        p1.append(pair[1])
    return {"method": "venn_abers", "edges": [float(e) for e in edges], "p0": p0, "p1": p1}


def bootstrap_indices(size: int, member: int, key: str) -> NDArray[np.int64]:
    generator = np.random.default_rng(seed_for("risk", "bootstrap-member", key, member))
    return generator.integers(0, size, size=size)


def bootstrap_interval(fit_member: Callable[[int], dict[str, Any]], members: int = MEMBERS) -> dict[str, Any]:
    """The ``bootstrap`` interval block; ``fit_member(i)`` returns ``{"scorer", "calibrator"}`` for member ``i``."""
    return {"method": "bootstrap", "members": [fit_member(i) for i in range(members)], "lower": LOWER, "upper": UPPER}


def wilson(positives: float, total: float) -> tuple[float, float]:
    if total == 0:
        return 0.0, 1.0
    rate = positives / total
    denominator = 1.0 + Z**2 / total
    centre = (rate + Z**2 / (2 * total)) / denominator
    half = Z * np.sqrt(rate * (1 - rate) / total + Z**2 / (4 * total**2)) / denominator
    return float(centre - half), float(centre + half)


@dataclass(frozen=True)
class Coverage:
    group_coverage: float
    inside_share: float
    mean_width: float
    groups: list[dict[str, float]]

    def summary(self) -> dict[str, Any]:
        return {
            "group_coverage": self.group_coverage,
            "inside_share": self.inside_share,
            "mean_width": self.mean_width,
            "groups": self.groups,
        }


def coverage(
    y: NDArray[np.int64], p: NDArray[np.float64], low: NDArray[np.float64], high: NDArray[np.float64]
) -> Coverage:
    order = np.argsort(p, kind="stable")
    groups, covered, inside = [], 0, 0
    for chunk in np.array_split(order, min(GROUPS, max(1, len(order)))):
        if len(chunk) == 0:
            continue
        rate = float(y[chunk].mean())
        a, b = wilson(float(y[chunk].sum()), float(len(chunk)))
        lo, hi = float(low[chunk].mean()), float(high[chunk].mean())
        hit = lo <= b and hi >= a
        covered += len(chunk) if hit else 0
        inside += len(chunk) if lo <= rate <= hi else 0
        groups.append(
            {
                "items": len(chunk),
                "mean_estimate": float(p[chunk].mean()),
                "observed": rate,
                "wilson_low": a,
                "wilson_high": b,
                "interval_low": lo,
                "interval_high": hi,
                "covered": float(hit),
            }
        )
    total = max(1, len(y))
    return Coverage(covered / total, inside / total, float(np.mean(high - low)) if len(y) else 0.0, groups)


def choose_method(results: dict[str, Coverage]) -> str:
    meeting = [name for name, result in results.items() if result.group_coverage >= COVERAGE_TARGET]
    if meeting:
        return min(meeting, key=lambda name: (results[name].mean_width, name))
    return max(results, key=lambda name: (results[name].group_coverage, -results[name].mean_width))
