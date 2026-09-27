"""Resolver train and evaluate: the steps behind ``bank-ml resolver train|evaluate`` and ``make train``.

``train`` builds the dataset from gold, fits the LightGBM ranker, scores it and the rule baseline on dev, logs the
run, registers the artifact with its dev metrics, and points ``candidate`` at it. ``evaluate`` loads the artifact
through the registry (the ``bank_agent`` adapter), scores both models on test per use, runs the silver-label
secondary evaluation, exports the silver verification sheet, and writes the evaluation JSON and
``docs/evaluation/resolver.md``.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np

from bank_agent.adapters.models.lgbm_resolver import LgbmResolverArtifact, LgbmTransactionResolver
from bank_agent.adapters.models.registry import FilesystemModelStore
from bank_agent.domain.errors import ModelArtifactNotFoundError
from bank_ml.common.paths import ARTIFACTS_DIR, DOCS_EVALUATION_DIR, GOLD_DIR, LABELING_DIR
from bank_ml.common.reports import generated_now, git_sha
from bank_ml.common.tracking import Tracker
from bank_ml.resolver import silver
from bank_ml.resolver.dataset import USE_TYPES, ResolverConfig, ResolverDataset, build_dataset, windows
from bank_ml.resolver.evaluate import Outcomes, evaluate, failures
from bank_ml.resolver.gold import GoldReader
from bank_ml.resolver.models import UNFITTED, PortModel, ResolverModel, fit_lgbm, rules_baseline

EXPERIMENT = "resolver"
RULES = "resolver:rules@1"
SILVER_SHEET = "resolver_silver_sample.csv"


def dev_metrics(model: ResolverModel, dataset: ResolverDataset) -> dict[str, float]:
    outcomes = Outcomes(model.name, dataset.split("dev"), model)
    multi = np.array([len(q.candidates) >= 2 for q in outcomes.queries], dtype=bool)
    two, every = outcomes.summary(multi), outcomes.summary()
    return {
        "dev_top1": two["top1"]["estimate"],
        "dev_mrr": two["mrr"]["estimate"],
        "dev_coverage": every["coverage"]["estimate"],
        "dev_wrong_rate": every["wrong_rate"]["estimate"],
        "dev_correct_clarify": every["correct_clarify"]["estimate"],
        "dev_absent_false_auto": every["absent_false_auto"]["estimate"],
    }


def train(
    store: FilesystemModelStore,
    tracker: Tracker,
    gold_dir: Path = GOLD_DIR,
    config: ResolverConfig | None = None,
    artifacts: Path = ARTIFACTS_DIR,
) -> tuple[ResolverDataset, str]:
    dataset = build_dataset(gold_dir, config)
    card_dir = artifacts / "datasets" / "resolver" / dataset.card.content_hash[:12]
    dataset.card.write(card_dir)
    baseline = dev_metrics(rules_baseline(), dataset)
    fitted = fit_lgbm(dataset.split("train"), dataset.split("dev"))
    ranker = PortModel("lgbm", LgbmTransactionResolver(LgbmResolverArtifact.model_validate(fitted.artifact), UNFITTED))
    metrics = dev_metrics(ranker, dataset)
    commit = git_sha()
    runs = artifacts / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    artifact_file = runs / "resolver_lgbm.json"
    artifact_file.write_text(json.dumps(fitted.artifact, sort_keys=True), encoding="utf-8")
    run_id = tracker.log_run(
        EXPERIMENT,
        "train resolver:lgbm",
        {**fitted.params, "margin": fitted.margin.threshold, "target_wrong": fitted.margin.target},
        {**metrics, "baseline_dev_top1": baseline["dev_top1"]},
        {"dataset_hash": dataset.card.content_hash, "dataset_version": dataset.card.version, "git_sha": commit},
        {"dataset": card_dir / "card.json", "model": artifact_file},
    )
    metadata = {
        "metrics": metrics,
        "baseline": RULES,
        "baseline_metrics": baseline,
        "dataset_hash": dataset.card.content_hash,
        "dataset_version": dataset.card.version,
        "git_sha": commit,
        "params": fitted.params,
        "margin": fitted.margin.__dict__,
        "mlflow_run_id": run_id or "",
    }
    resolved = store.register("resolver:lgbm", fitted.artifact, metadata)
    store.set_alias(
        "resolver:lgbm", "candidate", resolved.ref.version, {"set_by": "bank-ml resolver train", "git_sha": commit}
    )
    return dataset, str(resolved.ref)


def evaluate_all(
    store: FilesystemModelStore,
    tracker: Tracker,
    *,
    alias: str = "candidate",
    gold_dir: Path = GOLD_DIR,
    config: ResolverConfig | None = None,
    report: Path | None = DOCS_EVALUATION_DIR / "resolver.md",
    labeling_dir: Path = LABELING_DIR,
    artifacts: Path = ARTIFACTS_DIR,
) -> dict[str, Any]:
    try:
        resolved = store.registry.resolve("resolver:lgbm", alias)
    except ModelArtifactNotFoundError:
        raise ModelArtifactNotFoundError(f"no resolver:lgbm@{alias}; run bank-ml resolver train first") from None
    dataset = build_dataset(gold_dir, config)
    if resolved.metadata.get("dataset_hash") != dataset.card.content_hash:
        raise ValueError("the gold data or dataset code changed since resolver:lgbm was trained; train again")
    models: dict[str, ResolverModel] = {
        "rules@1": rules_baseline(),
        "lgbm": PortModel("lgbm", LgbmTransactionResolver.load(resolved)),
    }
    result: dict[str, Any] = {
        "generated_at": generated_now().isoformat(),
        "git_sha": git_sha(),
        "alias": alias,
        "artifact": str(resolved.ref),
        "margin": resolved.metadata.get("margin"),
        "params": resolved.metadata.get("params"),
        "dataset": {"version": dataset.card.version, "hash": dataset.card.content_hash,
                    "rows_per_split": dict(dataset.card.rows_per_split), "notes": list(dataset.card.notes)},
        "models": {},
        "failures": {},
    }  # fmt: skip
    for name, model in models.items():
        per_use = {use: evaluate(Outcomes(f"{name}:{use}", dataset.split("test", use), model)) for use in USE_TYPES}
        result["models"][name] = {"test": per_use, "dev": dev_metrics(model, dataset)}
        result["failures"][name] = failures(Outcomes(name, dataset.split("test"), model))
    reader = GoldReader(gold_dir)
    try:
        matches = silver.match(reader)
        silver_queries = silver.queries(matches, reader, windows()["dispute"])
    finally:
        reader.close()
    sheet = labeling_dir / SILVER_SHEET
    result["silver"] = {
        "counts": silver.counts(matches),
        "sheet": silver.export_sheet(matches, sheet),
        "verification": silver.sheet_status(sheet),
        "models": {name: Outcomes(f"{name}:silver", silver_queries, model).summary() for name, model in models.items()},
    }
    (artifacts / "evaluations").mkdir(parents=True, exist_ok=True)
    output = artifacts / "evaluations" / "resolver.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True, default=str), encoding="utf-8")
    if report is not None:
        from bank_ml.resolver.report import render

        report.write_text(render(result), encoding="utf-8")
    metrics = {
        f"test_{key}_{use}_{name.replace('@', '_v')}": result["models"][name]["test"][use]["two_or_more_candidates"][
            key
        ]["estimate"]
        for name in models
        for use in USE_TYPES
        for key in ("top1", "mrr")
    }
    tags = {"dataset_hash": dataset.card.content_hash, "git_sha": result["git_sha"]}
    params = {"alias": alias, "artifact": str(resolved.ref)}
    tracker.log_run(EXPERIMENT, f"evaluate {alias}", params, metrics, tags, {"evaluation": output})
    return result
