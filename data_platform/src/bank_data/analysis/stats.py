"""Small, seeded statistics for the analysis: bootstrap intervals, agreement, association, spikes.

Every random draw uses a ``numpy.random.Generator`` seeded from the pre-registered seed, so the reports are
reproducible to the digit.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np
import numpy.typing as npt

_MAX_DRAWS_PER_CHUNK = 20_000_000
"""Upper bound on the random indices drawn at once when bootstrapping a mean (memory guard)."""


@dataclass(frozen=True)
class Interval:
    """A point estimate with its bootstrap interval; ``n`` is the number of observations behind it."""

    estimate: float | None
    low: float | None
    high: float | None
    n: int

    @classmethod
    def empty(cls) -> "Interval":
        return cls(None, None, None, 0)


def _quantiles(samples: npt.NDArray[np.float64], confidence: float) -> tuple[float, float]:
    alpha = (1.0 - confidence) / 2.0
    low, high = np.quantile(samples, [alpha, 1.0 - alpha])
    return float(low), float(high)


def proportion_interval(successes: int, n: int, *, resamples: int, seed: int, confidence: float) -> Interval:
    """Percentile bootstrap interval of a proportion.

    Resampling ``n`` Bernoulli outcomes with replacement and counting successes is a binomial draw with the
    observed rate, so the resamples are drawn as binomial counts: the same distribution, without
    materializing the outcomes.
    """
    if n < 0 or successes < 0 or successes > n:
        raise ValueError("need 0 <= successes <= n")
    if n == 0:
        return Interval.empty()
    rate = successes / n
    rng = np.random.default_rng(seed)
    samples = rng.binomial(n, rate, size=resamples).astype(np.float64) / n
    low, high = _quantiles(samples, confidence)
    return Interval(rate, low, high, n)


def mean_interval(
    values: Sequence[float] | npt.NDArray[np.float64], *, resamples: int, seed: int, confidence: float
) -> Interval:
    """Percentile bootstrap interval of a mean (NaN values are dropped first)."""
    array = np.asarray(values, dtype=np.float64)
    array = array[~np.isnan(array)]
    n = int(array.size)
    if n == 0:
        return Interval.empty()
    rng = np.random.default_rng(seed)
    means = np.empty(resamples, dtype=np.float64)
    chunk = max(1, min(resamples, _MAX_DRAWS_PER_CHUNK // n))
    done = 0
    while done < resamples:
        size = min(chunk, resamples - done)
        indices = rng.integers(0, n, size=(size, n))
        means[done : done + size] = array[indices].mean(axis=1)
        done += size
    low, high = _quantiles(means, confidence)
    return Interval(float(array.mean()), low, high, n)


def cohen_kappa(first: Sequence[str], second: Sequence[str]) -> float | None:
    """Cohen's kappa for two labelers over the same items; ``None`` when undefined (no items, or chance
    agreement of 1)."""
    if len(first) != len(second):
        raise ValueError("both labelers must label the same items")
    n = len(first)
    if n == 0:
        return None
    categories = sorted(set(first) | set(second))
    observed = sum(1 for a, b in zip(first, second, strict=True) if a == b) / n
    expected = sum((first.count(c) / n) * (second.count(c) / n) for c in categories)
    if expected >= 1.0:
        return None
    return (observed - expected) / (1.0 - expected)


def cramers_v(table: Sequence[Sequence[int]]) -> float | None:
    """Cramer's V of a contingency table (rows by columns of counts); ``None`` when undefined."""
    counts = np.asarray(table, dtype=np.float64)
    if counts.ndim != 2 or counts.size == 0:
        return None
    counts = counts[counts.sum(axis=1) > 0][:, counts.sum(axis=0) > 0]
    total = counts.sum()
    rows, columns = counts.shape
    if total == 0 or min(rows, columns) < 2:
        return None
    expected = np.outer(counts.sum(axis=1), counts.sum(axis=0)) / total
    chi_square = float(((counts - expected) ** 2 / expected).sum())
    return float(np.sqrt(chi_square / (total * (min(rows, columns) - 1))))


@dataclass(frozen=True)
class Spike:
    day: date
    volume: int
    baseline: float
    robust_z: float


def detect_spikes(days: Sequence[date], volumes: Sequence[int], *, window: int, threshold: float) -> list[Spike]:
    """Days whose volume exceeds the trailing ``window``-day median by more than ``threshold`` robust z-scores.

    The robust z-score is ``(volume - median) / (1.4826 * MAD)`` over the previous ``window`` days (the day
    itself excluded). Days without a full window, or with a zero MAD, are not tested.
    """
    if len(days) != len(volumes):
        raise ValueError("days and volumes must align")
    order = sorted(range(len(days)), key=lambda index: days[index])
    series = np.asarray([volumes[index] for index in order], dtype=np.float64)
    spikes: list[Spike] = []
    for position in range(window, len(series)):
        history = series[position - window : position]
        median = float(np.median(history))
        mad = float(np.median(np.abs(history - median))) * 1.4826
        if mad == 0:
            continue
        z = (float(series[position]) - median) / mad
        if z > threshold:
            spikes.append(Spike(days[order[position]], int(series[position]), median, z))
    return spikes
