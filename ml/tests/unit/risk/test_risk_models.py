"""The exported models, numpy scoring against the serving adapter, slices, and the promotion rule."""

import math
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from bank_agent_models import RISK_LGBM_ARTIFACT, RISK_LOGREG_ARTIFACT
from bank_ml.risk import models, scoring
from bank_ml.risk.promotion import check
from bank_ml.risk.slices import slice_report
from bank_ml.risk.training import point_metrics, train_ranges

CUTS = (0.20, 0.35, 0.01)


def matrix(size: int = 3000, seed: int = 3) -> tuple[np.ndarray, np.ndarray]:
    generator = np.random.default_rng(seed)
    score = generator.integers(400, 850, size).astype(float)
    tenure = generator.integers(0, 90, size).astype(float)
    count = generator.integers(1, 5, size).astype(float)
    utilization = generator.random(size)
    x = np.column_stack([score, tenure, count, utilization])
    x[generator.random(size) < 0.1, 0] = np.nan
    x[generator.random(size) < 0.2, 3] = np.nan
    probability = 1 - (1 - 0.12) ** count
    return x, (generator.random(size) < probability).astype(np.int64)


def test_logreg_export_reproduces_scikit_learn_and_learns_the_count() -> None:
    x, y = matrix()
    scorer = models.fit_logreg(x, y)
    assert scorer["weights"][2] > 0.2
    assert len(scorer["missing_weights"]) == 4


def test_lgbm_export_reproduces_lightgbm_and_respects_the_score_constraint() -> None:
    x, y = matrix()
    fitted = models.fit_lgbm(x[:2000], y[:2000], x[2000:], y[2000:])
    assert fitted.rounds >= 1
    grid = np.column_stack([np.linspace(300, 850, 50), np.full(50, 30.0), np.full(50, 2.0), np.full(50, 0.5)])
    raw = scoring.trees_raw(fitted.scorer, grid)
    assert np.all(np.diff(raw) <= 1e-12)
    fixed = models.fit_lgbm(x, y, rounds=5, seed_key="member-0")
    assert fixed.rounds == 5
    with pytest.raises(ValueError, match="early stopping"):
        models.fit_lgbm(x, y)


def test_score_band_baselines() -> None:
    x = np.array([[760.0, 1, 1, 0.1], [610.0, 1, 1, 0.1], [np.nan, 1, 1, 0.1]])
    assert models.score_band_shipped(x).tolist() == [0.06, 0.33, 0.5]
    rates = models.score_band_rates(x, np.array([0, 1, 1]))
    assert rates[740] == (1, 0)
    assert rates[0] == (1, 1)
    assert models.score_band_reestimated(x, rates).tolist() == [0.0, 1.0, 1.0]


@pytest.mark.parametrize("artifact", [RISK_LOGREG_ARTIFACT, RISK_LGBM_ARTIFACT], ids=["logreg", "lgbm"])
def test_numpy_scoring_equals_the_serving_adapter(artifact: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    x, _ = matrix(200)
    assert scoring.assert_matches_adapter(artifact, x) <= scoring.TOLERANCE
    broken = {**artifact, "calibrator": {"kind": "platt", "a": 2.0, "b": 0.0}}
    original = scoring.estimate
    monkeypatch.setattr(scoring, "estimate", lambda _artifact, rows: original(broken, rows))
    with pytest.raises(ValueError, match="differs"):
        scoring.assert_matches_adapter(artifact, x)


@pytest.mark.parametrize("mode", ["none", "zero", "nan"])
def test_numpy_trees_follow_lightgbm_missing_rules(mode: str) -> None:
    tree = {"feature": 3, "threshold": 0.5, "default_left": False, "missing": mode,
            "left": {"value": -1.0}, "right": {"value": 1.0}}  # fmt: skip
    artifact = {**RISK_LGBM_ARTIFACT, "scorer": {"kind": "trees", "trees": [tree]},
                "calibrator": {"kind": "identity"}}  # fmt: skip
    x = np.array([[700, 10, 1, math.nan], [700, 10, 1, 0.0], [700, 10, 1, 0.9], [700, 10, 1, 0.2]])
    assert scoring.assert_matches_adapter(artifact, x) <= scoring.TOLERANCE


def test_ranges_and_point_metrics() -> None:
    x, y = matrix(100)
    ranges = train_ranges(x)
    assert ranges[2][0] >= 1.0
    values = point_metrics(y, np.full(100, 0.3), "dev")
    assert set(values) == {"dev_roc_auc", "dev_pr_auc", "dev_brier", "dev_log_loss", "dev_ece"}


def test_slices_flag_small_cells_and_list_calibration_gaps() -> None:
    size = 2000
    rows = [SimpleNamespace(country="MX" if i % 2 else "CO", segment="tiny" if i < 20 else "basic",
                            income_band="lower", credit_product_count=1 + i % 3) for i in range(size)]  # fmt: skip
    y = np.array([i % 5 == 0 for i in range(size)], dtype=np.int64)
    p = np.where(np.array([r.country == "MX" for r in rows]), 0.35, 0.2)
    report = slice_report(rows, y, p, p - 0.01, p + 0.01, CUTS, "unit")
    countries = {e["group"]: e for e in report["country"]}
    assert countries["MX"]["listed"]
    assert "calibration gap" in countries["MX"]["reasons"]
    segments = {e["group"]: e for e in report["segment"]}
    assert segments["tiny"]["small_cell"]
    assert not segments["tiny"]["listed"]
    assert not any(e["listed"] for e in report["credit_products"])


def _evaluation(auc_low: float, pr_gain: float, ece: float) -> dict[str, Any]:
    def test(auc: float, pr: float, brier: float, ece_value: float) -> dict[str, Any]:
        return {k: {"estimate": v} for k, v in {"roc_auc": auc, "pr_auc": pr, "brier": brier, "ece": ece_value}.items()}

    reference = test(0.5, 0.17, 0.14, 0.01)
    diff = {"roc_auc": {"low": auc_low}}
    return {
        "models": {"score_band@1": {"test": reference}, "score_band_reestimated": {"test": reference},
                   "logreg": {"test": test(0.61, 0.17 + pr_gain, 0.139, ece)}},
        "comparisons": {"logreg": {"score_band@1": diff, "score_band_reestimated": diff}},
    }  # fmt: skip


def test_the_promotion_rule_needs_every_condition() -> None:
    assert check(_evaluation(0.09, 0.08, 0.01), "logreg").promote
    assert not check(_evaluation(-0.001, 0.08, 0.01), "logreg").promote
    assert not check(_evaluation(0.09, -0.01, 0.01), "logreg").promote
    refused = check(_evaluation(0.09, 0.08, 0.05), "logreg")
    assert not refused.promote
    assert any("ECE" in reason and reason.endswith("fail") for reason in refused.reasons)
