"""Metrics, calibration math, threshold selection on synthetic score distributions, and the bootstrap."""

import numpy as np
import pytest

from bank_ml.common.calibration import fit_temperature, negative_log_likelihood, softmax
from bank_ml.common.metrics import (
    Interval,
    class_scores,
    cluster_bootstrap,
    confusion,
    coverage_risk,
    encode,
    expected_calibration_error,
    macro_f1,
    reciprocal_rank,
    reliability,
)
from bank_ml.common.thresholds import apply_threshold, choose_threshold


def test_confusion_and_class_scores() -> None:
    truth = encode(["a", "a", "b", "c"], ["a", "b", "c"])
    predicted = encode(["a", "b", "b", "zz"], ["a", "b", "c"])
    matrix = confusion(truth, predicted, 3)
    assert matrix.tolist() == [[1, 1, 0], [0, 1, 0], [0, 0, 0]]
    scores = class_scores(matrix, np.bincount(truth, minlength=3))
    assert (scores[0].precision, scores[0].recall, scores[0].support) == (1.0, 0.5, 2)
    assert scores[1].precision == 0.5
    assert scores[2].f1 == 0.0
    assert macro_f1(truth, predicted, 3) == pytest.approx((2 / 3 + 2 / 3 + 0.0) / 3)
    assert macro_f1(np.array([], dtype=np.int64), np.array([], dtype=np.int64), 3) == 0.0


def test_reliability_and_ece_on_a_perfectly_calibrated_and_an_overconfident_model() -> None:
    confidence = np.array([0.9] * 10 + [0.6] * 10)
    calibrated = np.array([True] * 9 + [False] + [True] * 6 + [False] * 4)
    assert expected_calibration_error(confidence, calibrated) == pytest.approx(0.0)
    overconfident = np.array([True] * 5 + [False] * 5 + [True] * 3 + [False] * 7)
    assert expected_calibration_error(confidence, overconfident) == pytest.approx(0.35)
    bins = reliability(confidence, calibrated)
    assert [b.count for b in bins if b.count] == [10, 10]
    assert expected_calibration_error(np.array([]), np.array([], dtype=bool)) == 0.0


def test_coverage_risk_curve_groups_equal_confidences() -> None:
    confidence = np.array([0.9, 0.9, 0.5, 0.2])
    correct = np.array([True, False, True, False])
    assert coverage_risk(confidence, correct) == [(0.9, 0.5, 0.5), (0.5, 0.75, 1 / 3), (0.2, 1.0, 0.5)]


def test_threshold_selection_maximizes_coverage_within_the_target() -> None:
    generator = np.random.default_rng(0)
    confidence = generator.uniform(0, 1, 2000)
    correct = generator.uniform(0, 1, 2000) < confidence
    choice = choose_threshold(confidence, correct, target=0.1)
    assert choice.met
    assert choice.risk <= 0.1
    covered = confidence >= choice.threshold
    assert (~correct[covered]).mean() == pytest.approx(choice.risk)
    lower = confidence[confidence < choice.threshold].max()
    assert (~correct[confidence >= lower]).mean() > 0.1
    coverage, risk = apply_threshold(confidence, correct, choice.threshold)
    assert (coverage, risk) == pytest.approx((choice.coverage, choice.risk))


def test_threshold_selection_reports_an_unmet_target() -> None:
    choice = choose_threshold(np.array([0.9, 0.8]), np.array([False, False]), target=0.05)
    assert not choice.met
    assert choice.risk == 1.0
    assert not choose_threshold(np.array([]), np.array([], dtype=bool), 0.05).met
    assert apply_threshold(np.array([0.1]), np.array([True]), 0.5) == (0.0, 0.0)


def test_temperature_scaling_recovers_a_known_temperature() -> None:
    generator = np.random.default_rng(1)
    true_logits = generator.normal(0, 2, size=(4000, 4))
    labels = np.array([generator.choice(4, p=row) for row in softmax(true_logits)])
    assert fit_temperature(true_logits * 2.0, labels) == pytest.approx(2.0, abs=0.25)
    assert negative_log_likelihood(true_logits, labels, 1.0) < negative_log_likelihood(true_logits * 3, labels, 1.0)
    assert fit_temperature(true_logits[:0], labels[:0]) == 1.0


def test_cluster_bootstrap_widens_with_correlated_items() -> None:
    values = np.array([1.0] * 50 + [0.0] * 50)
    independent = cluster_bootstrap(list(range(100)), lambda idx: float(values[idx].mean()), name="i")
    clustered = cluster_bootstrap([i // 50 for i in range(100)], lambda idx: float(values[idx].mean()), name="c")
    assert independent.estimate == clustered.estimate == 0.5
    assert clustered.high - clustered.low > independent.high - independent.low
    single = cluster_bootstrap([0, 0], lambda idx: 1.0, name="s")
    assert single == Interval(1.0, 1.0, 1.0)
    assert single.fmt(2) == "1.00 [1.00, 1.00]"
    assert reciprocal_rank(None) == 0.0
    assert reciprocal_rank(4) == 0.25
