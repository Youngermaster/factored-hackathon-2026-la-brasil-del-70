"""``bank-ml risk evaluate``: the one scoring of the held-out test split, after every choice is frozen.

Learned models are loaded through the registry and the ``bank_agent`` adapter (which validates the artifact and
checks its digest); numpy scoring is checked against the adapter on a sample. The score-band baselines are scored as
shipped (fixed priors) and re-estimated on train. The result has headline metrics with bootstrap intervals, paired
differences against every reference, reliability tables, bands, interval coverage, flags, slices with the disparity
list, and an error analysis; it is written as JSON under ``data/artifacts/ml/evaluations`` and rendered into
``docs/evaluation/risk-estimator.md``.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from bank_agent.adapters.models.learned_risk import LearnedRiskEstimator
from bank_agent.adapters.models.registry import FilesystemModelStore, read_verified
from bank_agent.adapters.models.risk_features import FEATURE_NAMES
from bank_agent.adapters.models.score_band_risk import band_for
from bank_agent.adapters.system.clock import SystemClock
from bank_agent.adapters.system.ids import RandomIdGenerator
from bank_agent.domain.errors import ModelArtifactNotFoundError
from bank_ml.common.paths import ARTIFACTS_DIR, DOCS_EVALUATION_DIR, GOLD_DIR
from bank_ml.common.reports import generated_now, git_sha
from bank_ml.common.tracking import Tracker
from bank_ml.risk import metrics, models, scoring, slices, uncertainty
from bank_ml.risk.dataset import Arrays, RiskDataset, build_dataset
from bank_ml.risk.labels import DPD_THRESHOLD, LABEL_DEFINITION
from bank_ml.risk.training import CHECK_ROWS, EXPERIMENT, KINDS, registry_name

EVALUATION_FILE = "risk.json"
SHIPPED, REESTIMATED = "score_band@1", "score_band_reestimated"
REFERENCES: dict[str, tuple[str, ...]] = {"logreg": (SHIPPED, REESTIMATED), "lgbm": (SHIPPED, REESTIMATED, "logreg")}
ERROR_EXAMPLES = 5

Scored = tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]


def shipped_scores(x: NDArray[np.float64]) -> Scored:
    bands = [band_for(None if np.isnan(s) else int(s)) for s in x[:, models.SCORE]]
    return (
        np.array([float(b.probability) for b in bands]),
        np.array([float(b.low) for b in bands]),
        np.array([float(b.high) for b in bands]),
    )


def reestimated_scores(train: Arrays, x: NDArray[np.float64]) -> Scored:
    rates = models.score_band_rates(train.x, train.y)
    keys = np.array([models.band_key(s) for s in x[:, models.SCORE]])
    bounds = {key: uncertainty.wilson(p, n) for key, (n, p) in rates.items()}
    p = models.score_band_reestimated(x, rates)
    return p, np.array([bounds[k][0] for k in keys]), np.array([bounds[k][1] for k in keys])


def _load(store: FilesystemModelStore, kind: str, alias: str, dataset: RiskDataset) -> tuple[str, dict[str, Any]]:
    name = registry_name(kind)
    try:
        resolved = store.registry.resolve(name, alias)
    except ModelArtifactNotFoundError:
        raise ModelArtifactNotFoundError(f"no {name}@{alias}; run bank-ml risk train first") from None
    if resolved.metadata.get("dataset_hash") != dataset.card.content_hash:
        raise ValueError(f"the gold data or dataset code changed since {name} was trained; train again")
    LearnedRiskEstimator.load(resolved, SystemClock(), RandomIdGenerator())
    return str(resolved.ref), read_verified(resolved)


def flag_shares(artifact: dict[str, Any], x: NDArray[Any], low: NDArray[Any], high: NDArray[Any]) -> dict[str, float]:
    ranges = np.asarray(artifact["ranges"], dtype=np.float64)
    present = ~np.isnan(x)
    outside = present & ((x < ranges[:, 0]) | (x > ranges[:, 1]))
    return {
        "missing_features": float(np.isnan(x).any(axis=1).mean()),
        "out_of_distribution": float(outside.any(axis=1).mean()),
        "wide_interval": float((high - low > artifact["wide_width"]).mean()),
    }


def error_examples(test: Arrays, p: NDArray[np.float64]) -> dict[str, list[dict[str, Any]]]:
    """The most confident misses, with coarsened synthetic feature values and no identifier."""

    def describe(index: int) -> dict[str, Any]:
        row = test.x[index]
        coarse = [
            None if np.isnan(v) else round(float(v), -1 if name == "credit_score" else 1)
            for name, v in zip(FEATURE_NAMES, row, strict=True)
        ]
        return {
            "estimate": round(float(p[index]), 3),
            "label": int(test.y[index]),
            "features": dict(zip(FEATURE_NAMES, coarse, strict=True)),
        }

    negatives, positives = np.flatnonzero(test.y == 0), np.flatnonzero(test.y == 1)
    top_negatives = negatives[np.argsort(-p[negatives], kind="stable")][:ERROR_EXAMPLES]
    low_positives = positives[np.argsort(p[positives], kind="stable")][:ERROR_EXAMPLES]
    return {
        "high_estimate_negatives": [describe(i) for i in top_negatives],
        "low_estimate_positives": [describe(i) for i in low_positives],
    }


def evaluate_all(
    store: FilesystemModelStore,
    tracker: Tracker,
    *,
    alias: str = "candidate",
    gold_dir: Path = GOLD_DIR,
    report: Path | None = DOCS_EVALUATION_DIR / "risk-estimator.md",
    artifacts: Path = ARTIFACTS_DIR,
) -> dict[str, Any]:
    dataset = build_dataset(gold_dir)
    train, test = dataset.arrays("train"), dataset.arrays("test")
    cuts = slices.policy_cuts()
    scored: dict[str, Scored] = {SHIPPED: shipped_scores(test.x), REESTIMATED: reestimated_scores(train, test.x)}
    loaded: dict[str, dict[str, Any]] = {}
    for kind in KINDS:
        ref, artifact = _load(store, kind, alias, dataset)
        scoring.assert_matches_adapter(artifact, test.x[:CHECK_ROWS])
        scored[kind] = scoring.estimate(artifact, test.x)
        manifest = store.registry.resolve(registry_name(kind), alias).metadata
        loaded[kind] = {
            "artifact": ref,
            "params": manifest.get("params"),
            "dev_metrics": manifest.get("metrics"),
            "calibration_selection_log_loss": manifest.get("calibration_selection_log_loss"),
            "interval_choice": manifest.get("interval_choice"),
            "dev_bands": manifest.get("dev_bands"),
            "flags": flag_shares(artifact, test.x, scored[kind][1], scored[kind][2]),
        }
    y = test.y
    result: dict[str, Any] = {
        "generated_at": generated_now().isoformat(),
        "git_sha": git_sha(),
        "alias": alias,
        "label_definition": LABEL_DEFINITION,
        "dpd_threshold": DPD_THRESHOLD,
        "cuts": list(cuts),
        "dataset": {
            "version": dataset.card.version,
            "hash": dataset.card.content_hash,
            "snapshot": str(dataset.snapshot),
            "rows_per_split": dict(dataset.card.rows_per_split),
            "filters": list(dataset.card.filters),
            "label_distribution": dataset.card.label_distribution,
        },
        "learned": loaded,
        "models": {},
        "comparisons": {},
    }
    for name, (p, low, high) in scored.items():
        result["models"][name] = {
            "test": metrics.summary(y, p, f"risk:{name}"),
            "reliability": metrics.reliability_table(y, p),
            "bands": slices.band_table(y, p, low, high, cuts),
            "interval_coverage": uncertainty.coverage(y, p, low, high).summary(),
            "slices": slices.slice_report(test.rows, y, p, low, high, cuts, f"risk:{name}"),
        }
    for kind, references in REFERENCES.items():
        result["comparisons"][kind] = {
            reference: {
                m: metrics.paired_difference(y, scored[kind][0], scored[reference][0], m, f"{kind}-{reference}")
                for m in ("roc_auc", "pr_auc", "brier")
            }
            for reference in references
        }
    result["errors"] = {kind: error_examples(test, scored[kind][0]) for kind in KINDS}
    (artifacts / "evaluations").mkdir(parents=True, exist_ok=True)
    output = artifacts / "evaluations" / EVALUATION_FILE
    output.write_text(json.dumps(result, indent=2, sort_keys=True, default=str), encoding="utf-8")
    if report is not None:
        from bank_ml.risk.report import render

        report.write_text(render(result), encoding="utf-8")
    logged = {
        f"test_{key}_{name.replace('@', '_v')}": result["models"][name]["test"][key]["estimate"]
        for name in scored
        for key in metrics.METRICS
    }
    tags = {"dataset_hash": dataset.card.content_hash, "git_sha": result["git_sha"]}
    params = {"alias": alias, **{kind: loaded[kind]["artifact"] for kind in KINDS}}
    tracker.log_run(EXPERIMENT, f"evaluate {alias}", params, logged, tags, {"evaluation": output})
    return result
