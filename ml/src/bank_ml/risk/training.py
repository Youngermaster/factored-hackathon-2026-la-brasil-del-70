"""``bank-ml risk train``: fit, calibrate, attach the interval, register, and point ``candidate`` at each learned model.

Every choice uses train and dev only: LightGBM's rounds and the calibrators use the dev calibration half; the
calibrator kind and the interval method are chosen on the dev selection half. The artifact's band cut points come
from the policy pack. Numpy scoring is checked against the serving adapter before anything is registered. Test is
never touched here.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from bank_agent.adapters.models.registry import FilesystemModelStore
from bank_agent.adapters.models.risk_features import FEATURE_NAMES, FEATURES_ID
from bank_ml.common.paths import ARTIFACTS_DIR, GOLD_DIR
from bank_ml.common.reports import git_sha
from bank_ml.common.tracking import Tracker
from bank_ml.risk import calibration, models, scoring, uncertainty
from bank_ml.risk.dataset import Arrays, RiskDataset, build_dataset
from bank_ml.risk.labels import LABEL_DEFINITION
from bank_ml.risk.metrics import METRICS
from bank_ml.risk.slices import band_table, policy_cuts

EXPERIMENT = "risk_estimator"
KINDS = ("logreg", "lgbm")
WIDE_WIDTH = 0.10
CHECK_ROWS = 300


def registry_name(kind: str) -> str:
    return f"risk_estimator:{kind}"


def train_ranges(x: NDArray[np.float64]) -> list[list[float]]:
    return [[float(np.nanmin(column)), float(np.nanmax(column))] for column in x.T]


def point_metrics(y: NDArray[np.int64], p: NDArray[np.float64], prefix: str) -> dict[str, float]:
    return {f"{prefix}_{key}": round(float(metric(y, p)), 6) for key, metric in METRICS.items()}


@dataclass(frozen=True)
class Trained:
    kind: str
    artifact: dict[str, Any]
    params: dict[str, Any]
    calibration: dict[str, float]
    intervals: dict[str, dict[str, Any]]
    chosen_interval: str
    metrics: dict[str, float]
    bands: dict[str, Any]


def _fit_scorer(
    kind: str, train: Arrays, stop: Arrays | None, rounds: int | None, key: str
) -> tuple[dict[str, Any], int]:
    if kind == "logreg":
        return models.fit_logreg(train.x, train.y), 0
    fitted = models.fit_lgbm(
        train.x, train.y, stop.x if stop else None, stop.y if stop else None, rounds=rounds, seed_key=key
    )
    return fitted.scorer, fitted.rounds


def fit_kind(kind: str, dataset: RiskDataset, cuts: tuple[float, float, float], members: int) -> Trained:
    train, cal, sel = dataset.arrays("train"), dataset.arrays("calibration"), dataset.arrays("selection")
    scorer, rounds = _fit_scorer(kind, train, cal, None, "main")
    raw_cal, raw_sel = scoring.raw_scores(scorer, cal.x), scoring.raw_scores(scorer, sel.x)
    choice = calibration.choose(raw_cal, cal.y, raw_sel, sel.y)
    calibrator = choice.calibrator

    def member(index: int) -> dict[str, Any]:
        rows = uncertainty.bootstrap_indices(len(train.y), index, f"{kind}:train")
        resampled = Arrays(train.x[rows], train.y[rows], ())
        member_scorer, _ = _fit_scorer(kind, resampled, None, rounds or None, f"member-{index}")
        cal_rows = uncertainty.bootstrap_indices(len(cal.y), index, f"{kind}:calibration")
        raw = scoring.raw_scores(member_scorer, cal.x[cal_rows])
        return {"scorer": member_scorer, "calibrator": calibration.fit(calibrator["kind"], raw, cal.y[cal_rows])}

    edges = uncertainty.venn_edges(scoring.raw_scores(scorer, train.x))
    candidates = {
        "bootstrap": uncertainty.bootstrap_interval(member, members),
        "venn_abers": uncertainty.venn_abers(edges, raw_cal, cal.y),
    }
    p_sel = calibration.apply(calibrator, raw_sel)
    results = {}
    for method, block in candidates.items():
        low, high = scoring.bounds(block, sel.x, raw_sel)
        results[method] = uncertainty.coverage(sel.y, p_sel, np.minimum(low, p_sel), np.maximum(high, p_sel))
    chosen = uncertainty.choose_method(results)
    artifact: dict[str, Any] = {
        "format": "risk_classifier/1",
        "features": FEATURES_ID,
        "feature_names": list(FEATURE_NAMES),
        "label_definition": LABEL_DEFINITION,
        "scorer": scorer,
        "calibrator": calibrator,
        "interval": candidates[chosen],
        "cut_medium": cuts[0],
        "cut_high": cuts[1],
        "ranges": train_ranges(train.x),
        "wide_width": WIDE_WIDTH,
    }
    scoring.assert_matches_adapter(artifact, sel.x[:CHECK_ROWS])
    p, low, high = scoring.estimate(artifact, sel.x)
    params: dict[str, Any] = {
        "kind": kind,
        "calibrator": calibrator["kind"],
        "interval": chosen,
        "members": members,
        "venn_bins": len(edges) + 1,
        "wide_width": WIDE_WIDTH,
    }
    if kind == "lgbm":
        params |= {"rounds": rounds, **{k: v for k, v in models.LGBM_PARAMS.items() if k != "monotone_constraints"}}
    else:
        params |= {"C": models.LOGREG_C}
    return Trained(
        kind,
        artifact,
        params,
        choice.selection_log_loss,
        {m: r.summary() for m, r in results.items()},
        chosen,
        point_metrics(sel.y, p, "dev"),
        band_table(sel.y, p, low, high, cuts),
    )


def baseline_dev_metrics(dataset: RiskDataset) -> dict[str, dict[str, float]]:
    train, sel = dataset.arrays("train"), dataset.arrays("selection")
    rates = models.score_band_rates(train.x, train.y)
    return {
        "score_band@1": point_metrics(sel.y, models.score_band_shipped(sel.x), "dev"),
        "score_band_reestimated": point_metrics(sel.y, models.score_band_reestimated(sel.x, rates), "dev"),
    }


def train(
    store: FilesystemModelStore,
    tracker: Tracker,
    gold_dir: Path = GOLD_DIR,
    artifacts: Path = ARTIFACTS_DIR,
    members: int = uncertainty.MEMBERS,
) -> tuple[RiskDataset, dict[str, str]]:
    dataset = build_dataset(gold_dir)
    card_dir = artifacts / "datasets" / "risk" / dataset.card.content_hash[:12]
    dataset.card.write(card_dir)
    cuts = policy_cuts()
    baselines = baseline_dev_metrics(dataset)
    commit = git_sha()
    runs = artifacts / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    refs: dict[str, str] = {}
    for kind in KINDS:
        trained = fit_kind(kind, dataset, cuts, members)
        artifact_file = runs / f"risk_{kind}.json"
        artifact_file.write_text(json.dumps(trained.artifact, sort_keys=True), encoding="utf-8")
        coverage_metrics = {f"dev_{m}_group_coverage": r["group_coverage"] for m, r in trained.intervals.items()}
        run_id = tracker.log_run(
            EXPERIMENT,
            f"train {registry_name(kind)}",
            trained.params,
            {**trained.metrics, **coverage_metrics},
            {"dataset_hash": dataset.card.content_hash, "dataset_version": dataset.card.version, "git_sha": commit},
            {"dataset": card_dir / "card.json", "model": artifact_file},
        )
        summaries = {m: {k: v for k, v in r.items() if k != "groups"} for m, r in trained.intervals.items()}
        metadata = {
            "metrics": trained.metrics,
            "baseline": "risk_estimator:score_band@1",
            "baseline_metrics": baselines,
            "calibration_selection_log_loss": trained.calibration,
            "interval_choice": {"chosen": trained.chosen_interval, "candidates": summaries},
            "dev_bands": trained.bands,
            "label_definition": LABEL_DEFINITION,
            "cuts": list(cuts),
            "dataset_hash": dataset.card.content_hash,
            "dataset_version": dataset.card.version,
            "git_sha": commit,
            "params": trained.params,
            "mlflow_run_id": run_id or "",
        }
        resolved = store.register(registry_name(kind), trained.artifact, metadata)
        store.set_alias(
            registry_name(kind), "candidate", resolved.ref.version, {"set_by": "bank-ml risk train", "git_sha": commit}
        )
        refs[kind] = str(resolved.ref)
    return dataset, refs
