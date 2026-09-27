import math
from datetime import date, timedelta

import pytest

from bank_data.analysis.stats import Interval, cohen_kappa, cramers_v, detect_spikes, mean_interval, proportion_interval


def test_proportion_interval_brackets_the_rate_and_is_reproducible() -> None:
    first = proportion_interval(30, 100, resamples=1000, seed=7, confidence=0.95)
    second = proportion_interval(30, 100, resamples=1000, seed=7, confidence=0.95)
    assert first == second
    assert first.estimate == pytest.approx(0.3)
    assert first.low is not None
    assert first.high is not None
    assert first.low < 0.3 < first.high
    # The normal approximation gives 0.3 +/- 0.09; the percentile bootstrap lands close to it.
    assert first.low == pytest.approx(0.21, abs=0.02)
    assert first.high == pytest.approx(0.39, abs=0.02)
    assert first.n == 100


def test_proportion_interval_of_a_certain_outcome_has_no_width() -> None:
    interval = proportion_interval(20, 20, resamples=1000, seed=7, confidence=0.95)
    assert (interval.estimate, interval.low, interval.high) == (1.0, 1.0, 1.0)


def test_proportion_interval_without_observations_is_empty() -> None:
    assert proportion_interval(0, 0, resamples=1000, seed=7, confidence=0.95) == Interval.empty()


def test_proportion_interval_rejects_impossible_counts() -> None:
    with pytest.raises(ValueError, match="successes"):
        proportion_interval(5, 4, resamples=1000, seed=7, confidence=0.95)


def test_mean_interval_drops_missing_values_and_is_reproducible() -> None:
    values = [1.0, 2.0, 3.0, 4.0, float("nan")]
    first = mean_interval(values, resamples=1000, seed=7, confidence=0.95)
    assert first == mean_interval(values, resamples=1000, seed=7, confidence=0.95)
    assert first.estimate == pytest.approx(2.5)
    assert first.n == 4
    assert first.low is not None
    assert first.high is not None
    assert 1.0 <= first.low < 2.5 < first.high <= 4.0


def test_mean_interval_of_constant_values_has_no_width() -> None:
    interval = mean_interval([5.0] * 50, resamples=1000, seed=7, confidence=0.95)
    assert (interval.estimate, interval.low, interval.high) == (5.0, 5.0, 5.0)


def test_mean_interval_without_values_is_empty() -> None:
    assert mean_interval([float("nan")], resamples=1000, seed=7, confidence=0.95) == Interval.empty()


def test_cohen_kappa_matches_a_hand_computed_example() -> None:
    # Observed agreement 0.7; chance agreement 0.5 * 0.6 + 0.5 * 0.4 = 0.5; kappa = 0.2 / 0.5 = 0.4.
    first = ["yes"] * 5 + ["no"] * 5
    second = ["yes"] * 4 + ["no"] + ["yes"] * 2 + ["no"] * 3
    assert cohen_kappa(first, second) == pytest.approx(0.4)


def test_cohen_kappa_is_one_for_perfect_agreement_and_undefined_without_variation() -> None:
    assert cohen_kappa(["yes", "no", "unclear"], ["yes", "no", "unclear"]) == pytest.approx(1.0)
    assert cohen_kappa(["yes", "yes"], ["yes", "yes"]) is None
    assert cohen_kappa([], []) is None
    with pytest.raises(ValueError, match="same items"):
        cohen_kappa(["yes"], [])


def test_cramers_v_is_zero_for_independence_and_one_for_perfect_association() -> None:
    assert cramers_v([[10, 10], [20, 20]]) == pytest.approx(0.0)
    assert cramers_v([[10, 0], [0, 10]]) == pytest.approx(1.0)
    assert cramers_v([[10, 10]]) is None
    assert cramers_v([]) is None


def test_detect_spikes_flags_a_day_far_above_the_trailing_median() -> None:
    start = date(2024, 1, 1)
    volumes = [100 + (index % 3) for index in range(40)]
    volumes[35] = 200
    days = [start + timedelta(days=index) for index in range(40)]
    spikes = detect_spikes(days, volumes, window=28, threshold=3.5)
    assert [spike.day for spike in spikes] == [days[35]]
    assert spikes[0].baseline == pytest.approx(101.0)
    assert spikes[0].robust_z > 3.5
    assert not math.isnan(spikes[0].robust_z)


def test_detect_spikes_skips_windows_without_variation() -> None:
    days = [date(2024, 1, 1) + timedelta(days=index) for index in range(10)]
    assert detect_spikes(days, [5] * 9 + [50], window=5, threshold=3.5) == []
    with pytest.raises(ValueError, match="align"):
        detect_spikes(days, [1], window=5, threshold=3.5)
