"""Calibration, Venn-Abers, the bootstrap ensemble, coverage, bands with the borderline case, and the metrics."""

import numpy as np
import pytest
from sklearn.metrics import average_precision_score, roc_auc_score

from bank_ml.risk import calibration, metrics, uncertainty
from bank_ml.risk.slices import band_table, bands, borderline

CUTS = (0.20, 0.35, 0.01)


def synthetic(size: int = 4000, seed: int = 7) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Scores with a known true probability ``sigmoid(logit)``; the raw score is a miscalibrated ``3 * logit``."""
    generator = np.random.default_rng(seed)
    logit = generator.normal(-1.5, 0.8, size)
    y = (generator.random(size) < calibration.sigmoid(logit)).astype(np.int64)
    return 3.0 * logit, y, calibration.sigmoid(logit)


def test_calibrators_fit_and_apply_like_the_serving_maps() -> None:
    raw, y, _ = synthetic()
    platt = calibration.fit("platt", raw, y)
    assert platt["a"] == pytest.approx(1 / 3, abs=0.08)
    iso = calibration.fit("isotonic", raw, y)
    assert all(b > a for a, b in zip(iso["x"], iso["x"][1:], strict=False))
    assert calibration.apply(iso, np.array([-100.0]))[0] == iso["y"][0]
    assert calibration.apply({"kind": "identity"}, np.array([0.0]))[0] == 0.5
    with pytest.raises(ValueError, match="unknown"):
        calibration.fit("beta", raw, y)
    with pytest.raises(ValueError, match="unknown"):
        calibration.apply({"kind": "beta"}, raw)


def test_the_dev_choice_prefers_a_calibrator_over_a_miscalibrated_sigmoid() -> None:
    raw, y, _ = synthetic()
    choice = calibration.choose(raw[:2000], y[:2000], raw[2000:], y[2000:])
    assert choice.calibrator["kind"] in {"platt", "isotonic"}
    assert choice.selection_log_loss["identity"] > min(choice.selection_log_loss.values())


def test_pava_pools_violators_with_weights() -> None:
    fitted = uncertainty.pava(np.array([0.1, 0.5, 0.3, 0.9]), np.array([1.0, 1.0, 3.0, 1.0]))
    assert fitted.tolist() == pytest.approx([0.1, 0.35, 0.35, 0.9])


def test_venn_abers_gives_ordered_intervals_that_cover_a_calibrated_distribution() -> None:
    raw, y, truth = synthetic(8000)
    edges = uncertainty.venn_edges(raw[:4000], bins=20)
    block = uncertainty.venn_abers(edges, raw[4000:6000], y[4000:6000])
    assert len(block["p0"]) == len(edges) + 1
    assert all(a <= b for a, b in zip(block["p0"], block["p1"], strict=True))
    position = np.searchsorted(edges, raw[6000:], side="right")
    p0, p1 = np.array(block["p0"])[position], np.array(block["p1"])[position]
    middle = p1 / (1 - p0 + p1)
    result = uncertainty.coverage(y[6000:], middle, np.minimum(p0, middle), np.maximum(p1, middle))
    assert result.group_coverage >= 0.9
    assert float(np.mean(np.abs(middle - truth[6000:]))) < 0.05


def test_venn_edges_sit_between_distinct_scores() -> None:
    raw = np.repeat(np.array([-2.0, -1.0, 0.5]), 100)
    edges = uncertainty.venn_edges(raw, bins=4)
    assert not set(edges.tolist()) & {-2.0, -1.0, 0.5}
    assert edges.tolist() == [-1.5, -0.25]


def test_bootstrap_interval_collects_members_and_indices_are_seeded() -> None:
    block = uncertainty.bootstrap_interval(lambda i: {"scorer": {"id": i}, "calibrator": {"kind": "identity"}}, 3)
    assert block["method"] == "bootstrap"
    assert [m["scorer"]["id"] for m in block["members"]] == [0, 1, 2]
    assert (block["lower"], block["upper"]) == (0.025, 0.975)
    first = uncertainty.bootstrap_indices(50, 1, "k")
    assert np.array_equal(first, uncertainty.bootstrap_indices(50, 1, "k"))
    assert not np.array_equal(first, uncertainty.bootstrap_indices(50, 2, "k"))


def test_coverage_and_the_pre_registered_choice() -> None:
    y = np.array([0, 1] * 50)
    p = np.full(100, 0.5)
    wide = uncertainty.coverage(y, p, p - 0.2, p + 0.2)
    narrow = uncertainty.coverage(y, p, p - 0.01, p + 0.01)
    off = uncertainty.coverage(y, p + 0.4, p + 0.39, p + 0.41)
    assert (wide.group_coverage, narrow.group_coverage, off.group_coverage) == (1.0, 1.0, 0.0)
    assert uncertainty.choose_method({"bootstrap": wide, "venn_abers": narrow}) == "venn_abers"
    assert uncertainty.choose_method({"bootstrap": off, "venn_abers": wide}) == "venn_abers"
    assert uncertainty.choose_method({"bootstrap": off, "venn_abers": off}) == "bootstrap"
    assert wide.summary()["groups"]
    assert uncertainty.wilson(0, 0) == (0.0, 1.0)
    low, high = uncertainty.wilson(17, 100)
    assert low < 0.17 < high


def test_bands_follow_the_cut_points_and_the_borderline_rule_matches_the_service() -> None:
    assert bands(np.array([0.1999, 0.2, 0.3499, 0.35]), 0.20, 0.35).tolist() == ["low", "medium", "medium", "high"]
    low = np.array([0.18, 0.10, 0.215, 0.33, 0.30])
    high = np.array([0.21, 0.185, 0.30, 0.345, 0.339])
    assert borderline(low, high, CUTS[:2], CUTS[2]).tolist() == [True, False, False, True, False]
    table = band_table(np.array([0, 1, 0]), np.array([0.1, 0.25, 0.4]), np.array([0.09, 0.2, 0.39]),
                       np.array([0.11, 0.3, 0.41]), CUTS)  # fmt: skip
    assert [row["customers"] for row in table["bands"]] == [1, 1, 1]
    assert table["borderline_share"] == pytest.approx(1 / 3)


def test_metrics_match_scikit_learn_and_bootstrap_is_deterministic() -> None:
    raw, y, _ = synthetic(2000)
    p = calibration.sigmoid(raw / 3)
    rounded = np.round(p, 2)
    assert metrics.roc_auc(y, rounded) == pytest.approx(roc_auc_score(y, rounded))
    assert metrics.pr_auc(y, p) == pytest.approx(average_precision_score(y, p))
    assert np.isnan(metrics.roc_auc(np.zeros(3, dtype=np.int64), p[:3]))
    assert np.isnan(metrics.pr_auc(np.zeros(3, dtype=np.int64), p[:3]))
    first = metrics.summary(y, p, "unit", samples=50)
    assert first == metrics.summary(y, p, "unit", samples=50)
    assert first["roc_auc"]["low"] <= first["roc_auc"]["estimate"] <= first["roc_auc"]["high"]
    same = metrics.paired_difference(y, p, p, "roc_auc", "unit")
    assert (same["estimate"], same["low"], same["high"]) == (0.0, 0.0, 0.0)
    single = metrics.bootstrap(1, lambda idx: 1.0, "one")
    assert single == {"estimate": 1.0, "low": 1.0, "high": 1.0}
    assert metrics.reliability_table(y, p)[0]["lower"] == 0.0
