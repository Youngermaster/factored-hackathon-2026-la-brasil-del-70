"""Resolver models: the shipped rule baseline and a LightGBM lambdarank ranker over the shared features.

LightGBM trains with a fixed seed, one thread, and ``deterministic=True``; the number of boosting rounds comes from
early stopping on dev NDCG@1. The booster's ``dump_model()`` is converted to the ``lgbm_ranker/1`` node format
(numerical ``<=`` splits only, anything else is refused), and every prediction afterwards goes through the
``bank_agent`` adapter. The "none of these" score and the clear-winner margin are chosen together on dev: for each
none score on a grid (quantiles of the dev top scores), the lowest margin whose wrong-transaction rate among
auto-selected queries is at most ``TARGET_WRONG``; the pair with the largest coverage that also auto-selects at most
``TARGET_ABSENT`` of the target-absent queries wins.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import lightgbm as lgb
import numpy as np

from bank_agent.adapters.models.lgbm_resolver import LgbmResolverArtifact, LgbmTransactionResolver
from bank_agent.adapters.models.resolver_features import FEATURE_NAMES, FEATURES_ID, candidate_features, plausible
from bank_agent.adapters.models.rules_resolver import RuleTransactionResolver
from bank_agent.domain.intelligence import ModelComponent, ModelRef, TransactionResolution
from bank_ml.common.seeds import seed_for
from bank_ml.common.thresholds import ThresholdChoice, choose_threshold
from bank_ml.resolver.dataset import Query

TARGET_WRONG = 0.02
TARGET_ABSENT = 0.05
NULL_FLOOR = -50.0
UNFITTED = ModelRef(component=ModelComponent.RESOLVER, name="unfitted", version="0")
PARAMS: dict[str, Any] = {
    "objective": "lambdarank",
    "metric": "ndcg",
    "eval_at": [1],
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_data_in_leaf": 20,
    "deterministic": True,
    "force_row_wise": True,
    "num_threads": 1,
    "verbose": -1,
}
MAX_ROUNDS = 500
EARLY_STOPPING = 30


class ResolverModel(Protocol):
    name: str

    def rank(self, query: Query) -> TransactionResolution: ...


class PortModel:
    """Any ``TransactionResolver`` (baseline or loaded adapter) applied to a query."""

    def __init__(self, name: str, resolver: Any) -> None:
        self.name = name
        self._resolver = resolver

    def rank(self, query: Query) -> TransactionResolution:
        resolution: TransactionResolution = self._resolver.rank(query.descriptor, query.candidates, now=query.now)
        return resolution


def rules_baseline() -> PortModel:
    return PortModel("rules@1", RuleTransactionResolver())


def matrix(queries: Sequence[Query]) -> tuple[np.ndarray, np.ndarray, list[int]]:
    rows: list[list[float]] = []
    labels: list[int] = []
    groups: list[int] = []
    for query in queries:
        features = candidate_features(query.descriptor, query.candidates, query.now)
        rows.extend(features)
        labels.extend(int(txn.transaction_id == query.target_id) for txn in query.candidates)
        groups.append(len(features))
    return np.array(rows, dtype=np.float64), np.array(labels, dtype=np.int64), groups


def _node(raw: dict[str, Any]) -> dict[str, Any]:
    if "leaf_value" in raw:
        return {"value": float(raw["leaf_value"])}
    if raw.get("decision_type") != "<=":
        raise ValueError(f"unsupported split {raw.get('decision_type')}; only numerical <= splits are served")
    missing = {"None": "none", "Zero": "zero", "NaN": "nan"}[raw.get("missing_type", "None")]
    return {
        "feature": int(raw["split_feature"]),
        "threshold": float(raw["threshold"]),
        "default_left": bool(raw.get("default_left", True)),
        "missing": missing,
        "left": _node(raw["left_child"]),
        "right": _node(raw["right_child"]),
    }


def convert(dump: dict[str, Any]) -> list[dict[str, Any]]:
    return [_node(tree["tree_structure"]) for tree in dump["tree_info"]]


@dataclass(frozen=True)
class FittedRanker:
    artifact: dict[str, Any]
    params: dict[str, Any]
    margin: ThresholdChoice
    booster: lgb.Booster


def auto_outcomes(model: ResolverModel, queries: Sequence[Query]) -> tuple[np.ndarray, np.ndarray]:
    """Per query: the margin (0 without a ranking) and whether the top candidate is the target."""
    margins, correct = [], []
    for query in queries:
        resolution = model.rank(query)
        top = resolution.ranked[0].transaction_id if resolution.ranked else None
        margins.append(resolution.margin if resolution.margin is not None and resolution.ranked else 0.0)
        correct.append(top is not None and top == query.target_id)
    return np.array(margins, dtype=np.float64), np.array(correct, dtype=bool)


def fit_lgbm(train: Sequence[Query], dev: Sequence[Query]) -> FittedRanker:
    x_train, y_train, g_train = matrix(train)
    x_dev, y_dev, g_dev = matrix([q for q in dev if q.target_id is not None])
    params = {**PARAMS, "seed": seed_for("resolver", "lgbm")}
    train_set = lgb.Dataset(x_train, y_train, group=g_train, feature_name=list(FEATURE_NAMES), free_raw_data=False)
    dev_set = lgb.Dataset(x_dev, y_dev, group=g_dev, reference=train_set)
    booster = lgb.train(
        params,
        train_set,
        num_boost_round=MAX_ROUNDS,
        valid_sets=[dev_set],
        callbacks=[lgb.early_stopping(EARLY_STOPPING, verbose=False)],
    )
    best = booster.best_iteration or booster.current_iteration()
    artifact: dict[str, Any] = {
        "format": "lgbm_ranker/1",
        "features": FEATURES_ID,
        "feature_names": list(FEATURE_NAMES),
        "trees": convert(booster.dump_model(num_iteration=best)),
        "margin": 0.0,
        "null_score": NULL_FLOOR,
    }
    null_score, choice, absent_rate = choose_null_and_margin(artifact, dev)
    artifact["null_score"] = round(null_score, 6)
    artifact["margin"] = round(min(1.0, max(0.0, choice.threshold)), 6)
    fitted_params = {k: v for k, v in params.items() if k != "eval_at"} | {
        "rounds": best,
        "trees": len(artifact["trees"]),
        "null_score": artifact["null_score"],
        "dev_absent_auto": absent_rate,
    }
    return FittedRanker(artifact, fitted_params, choice, booster)


def _ranker(artifact: dict[str, Any]) -> PortModel:
    return PortModel("lgbm", LgbmTransactionResolver(LgbmResolverArtifact.model_validate(artifact), UNFITTED))


def _top_raw_scores(artifact: dict[str, Any], queries: Sequence[Query]) -> list[float]:
    resolver = LgbmTransactionResolver(LgbmResolverArtifact.model_validate(artifact), UNFITTED)
    tops = []
    for query in queries:
        rows = [row for row in candidate_features(query.descriptor, query.candidates, query.now) if plausible(row)]
        if rows:
            tops.append(max(resolver.score_rows(rows)))
    return tops


def choose_null_and_margin(artifact: dict[str, Any], dev: Sequence[Query]) -> tuple[float, ThresholdChoice, float]:
    """The (none score, margin choice, dev target-absent auto rate) with the best dev coverage under both targets."""
    tops = _top_raw_scores(artifact, dev)
    quantiles: list[float] = list(np.quantile(tops, np.linspace(0.0, 0.6, 25))) if tops else []
    grid = sorted({NULL_FLOOR, *(float(value) for value in quantiles)})
    absent = np.array([q.target_id is None for q in dev], dtype=bool)
    options = []
    for null in grid:
        margins, correct = auto_outcomes(_ranker({**artifact, "null_score": null}), dev)
        choice = choose_threshold(margins, correct, TARGET_WRONG)
        threshold = max(0.0, choice.threshold)
        absent_rate = float((margins[absent] >= threshold).mean()) if absent.any() else 0.0
        met = choice.met and absent_rate <= TARGET_ABSENT
        options.append((met, choice.coverage if met else -absent_rate, -null, null, choice, absent_rate))
    best = max(options, key=lambda option: option[:3])
    return best[3], best[4], best[5]
