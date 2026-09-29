"""Interval estimates and repeated-run statistics, in pure Python (no SciPy in the harness).

- ``wilson``: the Wilson score interval, used for every proportion.
- ``clopper_pearson``: the exact binomial interval (two-sided), found by bisection on the binomial CDF.
- ``zero_event_bounds``: with zero events in n cases, the rule of three (3/n) and the exact one-sided 95% upper
  bound, ``1 - 0.05 ** (1 / n)``.
- ``pass_hat_k``: the probability that all k runs of a scenario succeed, ``C(c, k) / C(n, k)`` for c successes
  in n runs, averaged over scenarios.
- ``between_run_sd``: the standard deviation of a rate across runs.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

Z_95 = 1.959963984540054
_BISECTION_STEPS = 80


@dataclass(frozen=True)
class Interval:
    low: float
    high: float


def wilson(count: int, n: int, z: float = Z_95) -> Interval | None:
    """The Wilson score interval, or ``None`` when ``n`` is zero (not defined)."""
    if n == 0:
        return None
    p = count / n
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return Interval(max(0.0, centre - half), min(1.0, centre + half))


def _binomial_cdf(k: int, n: int, p: float) -> float:
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1))


def _solve(target: float, n: int, k: int) -> float:
    """The p where ``P(X <= k; n, p) == target`` (decreasing in p)."""
    low, high = 0.0, 1.0
    for _ in range(_BISECTION_STEPS):
        middle = (low + high) / 2
        if _binomial_cdf(k, n, middle) > target:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def clopper_pearson(count: int, n: int, alpha: float = 0.05) -> Interval | None:
    """The exact two-sided (1 - alpha) interval, or ``None`` when ``n`` is zero."""
    if n == 0:
        return None
    low = 0.0 if count == 0 else _solve(1 - alpha / 2, n, count - 1)
    high = 1.0 if count == n else _solve(alpha / 2, n, count)
    return Interval(low, high)


@dataclass(frozen=True)
class ZeroEventBounds:
    rule_of_three: float
    exact_upper_95: float


def zero_event_bounds(n: int) -> ZeroEventBounds | None:
    """Upper bounds on the event rate when none was observed in ``n`` cases."""
    if n == 0:
        return None
    return ZeroEventBounds(rule_of_three=min(1.0, 3 / n), exact_upper_95=1 - 0.05 ** (1 / n))


def pass_hat_k(successes: Sequence[tuple[int, int]], k: int) -> float | None:
    """Mean over scenarios of ``C(c, k) / C(n, k)``, for (successes c, runs n) with n >= k; ``None`` if none."""
    eligible = [(c, n) for c, n in successes if n >= k]
    if not eligible or k < 1:
        return None
    return sum(math.comb(c, k) / math.comb(n, k) for c, n in eligible) / len(eligible)


def between_run_sd(rates: Sequence[float]) -> float | None:
    """The sample standard deviation of a rate across runs; ``None`` with fewer than two runs."""
    return statistics.stdev(rates) if len(rates) >= 2 else None


def percentile(values: Sequence[float], q: float) -> float | None:
    """The nearest-rank percentile (``q`` in 0..100), or ``None`` for no values."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(q / 100 * len(ordered)))
    return ordered[rank - 1]
