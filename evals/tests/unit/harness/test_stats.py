"""Interval estimates and repeated-run statistics against published reference values."""

import pytest

from bank_evals.metrics.stats import (
    between_run_sd,
    clopper_pearson,
    pass_hat_k,
    percentile,
    wilson,
    zero_event_bounds,
)


def test_wilson_matches_the_reference_interval_for_18_of_20() -> None:
    interval = wilson(18, 20)
    assert interval is not None
    assert (round(interval.low, 3), round(interval.high, 3)) == (0.699, 0.972)


def test_wilson_is_not_defined_without_cases_and_stays_inside_zero_and_one() -> None:
    assert wilson(0, 0) is None
    zero, full = wilson(0, 10), wilson(10, 10)
    assert zero is not None
    assert zero.low == pytest.approx(0.0)
    assert full is not None
    assert full.high == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("count", "n", "low", "high"),
    [(0, 10, 0.0, 0.3085), (5, 10, 0.1871, 0.8129), (10, 10, 0.6915, 1.0)],
)
def test_clopper_pearson_matches_the_exact_binomial_interval(count: int, n: int, low: float, high: float) -> None:
    interval = clopper_pearson(count, n)
    assert interval is not None
    assert (round(interval.low, 4), round(interval.high, 4)) == (low, high)
    assert clopper_pearson(0, 0) is None


def test_zero_event_bounds_give_the_rule_of_three_and_the_exact_bound() -> None:
    bounds = zero_event_bounds(30)
    assert bounds is not None
    assert bounds.rule_of_three == pytest.approx(0.1)
    assert bounds.exact_upper_95 == pytest.approx(0.0950, abs=1e-4)
    assert zero_event_bounds(0) is None
    small = zero_event_bounds(2)
    assert small is not None
    assert small.rule_of_three == 1.0


def test_pass_hat_k_averages_the_chance_that_every_run_succeeds() -> None:
    assert pass_hat_k([(3, 3), (2, 3), (0, 3)], 2) == pytest.approx(4 / 9)
    assert pass_hat_k([(3, 3), (2, 3)], 1) == pytest.approx(5 / 6)
    assert pass_hat_k([(1, 1)], 2) is None
    assert pass_hat_k([(1, 1)], 0) is None


def test_between_run_sd_and_percentiles() -> None:
    assert between_run_sd([0.5]) is None
    assert between_run_sd([0.5, 0.7, 0.6]) == pytest.approx(0.1)
    assert percentile([], 50) is None
    assert percentile([5, 1, 3, 2, 4], 50) == 3
    assert percentile([5, 1, 3, 2, 4], 95) == 5
