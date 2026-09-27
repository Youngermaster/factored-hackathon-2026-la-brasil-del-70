"""Risk models over the shared ``risk_features@1`` matrix: the score-band baselines, logistic regression, and
LightGBM, each exported as a ``risk_classifier/1`` scorer (plain parameters, no pickles).

- ``score_band@1`` as shipped: the phase 09 adapter's fixed prior per credit score band.
- ``score_band`` re-estimated: the same bands with the observed train rate per band.
- ``logreg``: median imputation, one missing indicator per feature, standardization, L2 with C fixed at 1.0 (four
  features on tens of thousands of rows need no tuning).
- ``lgbm``: binary LightGBM, seeded, one thread, deterministic, a monotone decreasing constraint on the credit
  score, rounds chosen by early stopping on the dev calibration half (or fixed, for bootstrap members).
"""

from dataclasses import dataclass
from typing import Any

import lightgbm as lgb
import numpy as np
from numpy.typing import NDArray
from sklearn.linear_model import LogisticRegression

from bank_agent.adapters.models.risk_features import FEATURE_NAMES
from bank_agent.adapters.models.score_band_risk import SCORE_BANDS, UNKNOWN, band_for
from bank_ml.common.seeds import seed_for
from bank_ml.resolver.models import convert
from bank_ml.risk.scoring import linear_raw, trees_raw

SCORE = FEATURE_NAMES.index("credit_score")
LOGREG_C = 1.0
LGBM_PARAMS: dict[str, Any] = {
    "objective": "binary",
    "metric": "binary_logloss",
    "learning_rate": 0.1,
    "num_leaves": 7,
    "min_data_in_leaf": 200,
    "monotone_constraints": [-1 if name == "credit_score" else 0 for name in FEATURE_NAMES],
    "deterministic": True,
    "force_row_wise": True,
    "num_threads": 1,
    "verbose": -1,
}
MAX_ROUNDS = 400
EARLY_STOPPING = 30


def band_key(score: float) -> int:
    return UNKNOWN.min_score if np.isnan(score) else band_for(int(score)).min_score


def score_band_shipped(x: NDArray[np.float64]) -> NDArray[np.float64]:
    return np.array([float((band_for(None if np.isnan(s) else int(s))).probability) for s in x[:, SCORE]])


def score_band_rates(x: NDArray[np.float64], y: NDArray[np.int64]) -> dict[int, tuple[int, int]]:
    """``{band minimum score: (customers, positives)}`` on the rows given (train), the unknown band included."""
    keys = np.array([band_key(s) for s in x[:, SCORE]])
    bands = [band.min_score for band in SCORE_BANDS] + [UNKNOWN.min_score]
    return {key: (int((keys == key).sum()), int(y[keys == key].sum())) for key in bands}


def score_band_reestimated(x: NDArray[np.float64], rates: dict[int, tuple[int, int]]) -> NDArray[np.float64]:
    overall = sum(p for _, p in rates.values()) / max(1, sum(n for n, _ in rates.values()))
    table = {key: (p / n if n else overall) for key, (n, p) in rates.items()}
    return np.array([table[band_key(s)] for s in x[:, SCORE]])


def _design(
    x: NDArray[np.float64], impute: NDArray[Any], mean: NDArray[Any], scale: NDArray[Any]
) -> NDArray[np.float64]:
    absent = np.isnan(x)
    filled = np.where(absent, impute, x)
    return np.hstack([(filled - mean) / scale, absent.astype(np.float64)])


def fit_logreg(x: NDArray[np.float64], y: NDArray[np.int64]) -> dict[str, Any]:
    impute = np.array([np.nanmedian(x[:, i]) if (~np.isnan(x[:, i])).any() else 0.0 for i in range(x.shape[1])])
    filled = np.where(np.isnan(x), impute, x)
    mean, std = filled.mean(axis=0), filled.std(axis=0)
    scale = np.where(std > 0, std, 1.0)
    model = LogisticRegression(C=LOGREG_C, max_iter=2000).fit(_design(x, impute, mean, scale), y)
    width = x.shape[1]
    scorer = {
        "kind": "linear",
        "impute": [float(v) for v in impute],
        "mean": [float(v) for v in mean],
        "scale": [float(v) for v in scale],
        "weights": [float(v) for v in model.coef_[0][:width]],
        "missing_weights": [float(v) for v in model.coef_[0][width:]],
        "intercept": float(model.intercept_[0]),
    }
    check = model.decision_function(_design(x[:50], impute, mean, scale))
    if not np.allclose(check, linear_raw(scorer, x[:50]), atol=1e-9):
        raise ValueError("the exported logistic regression does not reproduce scikit-learn")
    return scorer


@dataclass(frozen=True)
class FittedTrees:
    scorer: dict[str, Any]
    rounds: int


def fit_lgbm(
    x: NDArray[np.float64],
    y: NDArray[np.int64],
    x_stop: NDArray[np.float64] | None = None,
    y_stop: NDArray[np.int64] | None = None,
    *,
    rounds: int | None = None,
    seed_key: str = "main",
) -> FittedTrees:
    params = {**LGBM_PARAMS, "seed": seed_for("risk", "lgbm", seed_key)}
    train_set = lgb.Dataset(x, y, feature_name=list(FEATURE_NAMES), free_raw_data=False)
    if rounds is None:
        if x_stop is None or y_stop is None:
            raise ValueError("early stopping needs the dev calibration rows")
        stop_set = lgb.Dataset(x_stop, y_stop, reference=train_set)
        booster = lgb.train(
            params,
            train_set,
            num_boost_round=MAX_ROUNDS,
            valid_sets=[stop_set],
            callbacks=[lgb.early_stopping(EARLY_STOPPING, verbose=False)],
        )
        best = booster.best_iteration or booster.current_iteration()
    else:
        booster = lgb.train(params, train_set, num_boost_round=rounds)
        best = rounds
    scorer = {"kind": "trees", "trees": convert(booster.dump_model(num_iteration=best))}
    native = booster.predict(x[:200], num_iteration=best, raw_score=True)
    if not np.allclose(native, trees_raw(scorer, x[:200]), atol=1e-9):
        raise ValueError("the exported trees do not reproduce LightGBM's raw scores")
    return FittedTrees(scorer, best)
