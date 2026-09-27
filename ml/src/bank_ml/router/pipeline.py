"""Router train and evaluate: the steps behind ``bank-ml router train|evaluate`` and ``make train``.

``train`` builds the dataset, fits the learned models, scores them and the keyword baseline on dev, logs each run to
MLflow, registers the artifacts with their dev metrics, and points ``candidate`` at them. ``evaluate`` loads the
artifacts through the registry (the ``bank_agent`` adapters, exactly as the API would), scores every model on test,
runs the robustness and transfer sets, and writes the evaluation JSON and ``docs/evaluation/router.md``.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bank_agent.adapters.models.embedding_router import EmbeddingIntentRouter, EmbeddingRouterArtifact
from bank_agent.adapters.models.registry import FilesystemModelStore
from bank_agent.adapters.models.tfidf_router import TfidfIntentRouter, TfidfRouterArtifact
from bank_agent.adapters.retrieval.embedding import Embedder
from bank_agent.domain.errors import ModelArtifactNotFoundError
from bank_ml.common.paths import ARTIFACTS_DIR, DOCS_EVALUATION_DIR
from bank_ml.common.reports import generated_now, git_sha
from bank_ml.common.tracking import Tracker
from bank_ml.router.corpus import CORPUS_DIR, load_lexicon
from bank_ml.router.dataset import RouterDataset, build_dataset, write_dataset
from bank_ml.router.evaluate import Scored, errors, evaluate, summary
from bank_ml.router.models import (
    UNFITTED,
    Fitted,
    MajorityBaseline,
    RoutePredictor,
    RouterModel,
    fit_embeddings,
    fit_tfidf,
    keyword_baseline,
)
from bank_ml.router.paraphrase import load_paraphrases
from bank_ml.router.robustness import language_detection, robustness, transfer
from bank_ml.router.transcripts import analyze
from bank_ml.router.validation import ValidationFiles, export, status

EXPERIMENT = "router"
KEYWORD = "router:keyword@1"
EmbedderFactory = Callable[[], Embedder | None]


def dev_metrics(scored: Scored) -> dict[str, float]:
    s = summary(scored)
    return {
        "dev_accuracy": s["accuracy"]["estimate"],
        "dev_macro_f1": s["macro_f1"]["estimate"],
        "dev_workflow_accuracy": s["workflow_accuracy"]["estimate"],
        "dev_high_stakes_recall_mean": s["high_stakes_recall_mean"],
        "dev_ece": s["ece"],
        "dev_coverage": s["coverage"]["estimate"],
        "dev_risk_at_threshold": s["risk_at_threshold"]["estimate"],
    }


@dataclass(frozen=True)
class TrainResult:
    dataset: RouterDataset
    registered: dict[str, str]
    skipped: dict[str, str]


def _register(
    store: FilesystemModelStore,
    tracker: Tracker,
    name: str,
    fitted: Fitted,
    predictor: RouterModel,
    dataset: RouterDataset,
    baseline: dict[str, float],
    card_dir: Path,
    runs_dir: Path,
) -> str:
    metrics = dev_metrics(Scored(name, dataset.split("dev"), predictor.predict(dataset.split("dev"))))
    commit = git_sha()
    runs_dir.mkdir(parents=True, exist_ok=True)
    artifact_file = runs_dir / f"{name.replace(':', '_')}.json"
    artifact_file.write_text(json.dumps(fitted.artifact, sort_keys=True), encoding="utf-8")
    run_id = tracker.log_run(
        EXPERIMENT,
        f"train {name}",
        {**fitted.params, "threshold": fitted.threshold.threshold, "target_risk": fitted.threshold.target},
        {**metrics, "baseline_dev_macro_f1": baseline["dev_macro_f1"]},
        {"dataset_hash": dataset.content_hash, "dataset_version": dataset.card.version, "git_sha": commit},
        {"dataset": card_dir / "card.json", "model": artifact_file},
    )
    metadata = {
        "metrics": metrics,
        "baseline": KEYWORD,
        "baseline_metrics": baseline,
        "dataset_hash": dataset.content_hash,
        "dataset_version": dataset.card.version,
        "git_sha": commit,
        "params": fitted.params,
        "threshold": fitted.threshold.__dict__,
        "mlflow_run_id": run_id or "",
    }
    resolved = store.register(name, fitted.artifact, metadata)
    store.set_alias(name, "candidate", resolved.ref.version, {"set_by": "bank-ml router train", "git_sha": commit})
    return str(resolved.ref)


def train(
    store: FilesystemModelStore,
    tracker: Tracker,
    embedder: EmbedderFactory,
    corpus_dir: Path = CORPUS_DIR,
    artifacts: Path = ARTIFACTS_DIR,
) -> TrainResult:
    dataset = build_dataset(corpus_dir)
    card_dir = write_dataset(dataset, artifacts / "datasets")
    runs_dir = artifacts / "runs"
    train_items, dev_items = dataset.split("train"), dataset.split("dev")
    keyword = keyword_baseline()
    baseline = dev_metrics(Scored(KEYWORD, dev_items, keyword.predict(dev_items)))
    registered: dict[str, str] = {}
    skipped: dict[str, str] = {}
    tfidf = fit_tfidf(train_items, dev_items)
    tfidf_router = TfidfIntentRouter(TfidfRouterArtifact.model_validate(tfidf.artifact), UNFITTED)
    registered["tfidf"] = _register(
        store,
        tracker,
        "router:tfidf",
        tfidf,
        RoutePredictor("tfidf", tfidf_router),
        dataset,
        baseline,
        card_dir,
        runs_dir,
    )
    encoder = embedder()
    if encoder is None:
        skipped["embeddings"] = "the ml extra (sentence-transformers) is not installed"
    else:
        fitted = fit_embeddings(train_items, dev_items, encoder)
        router = EmbeddingIntentRouter(EmbeddingRouterArtifact.model_validate(fitted.artifact), encoder, UNFITTED)
        registered["embeddings"] = _register(
            store,
            tracker,
            "router:embeddings",
            fitted,
            RoutePredictor("embeddings", router),
            dataset,
            baseline,
            card_dir,
            runs_dir,
        )
    return TrainResult(dataset, registered, skipped)


def _load_learned(
    store: FilesystemModelStore, alias: str, embedder: EmbedderFactory
) -> tuple[dict[str, RouterModel], dict[str, str], dict[str, Any], str | None]:
    models: dict[str, RouterModel] = {}
    refs: dict[str, str] = {}
    metadata: dict[str, Any] = {}
    skipped: str | None = None
    for short in ("tfidf", "embeddings"):
        try:
            resolved = store.registry.resolve(f"router:{short}", alias)
        except ModelArtifactNotFoundError:
            if short == "embeddings":
                skipped = f"no router:embeddings@{alias} is registered (the ml extra was absent at training)"
            continue
        if short == "tfidf":
            models[short] = RoutePredictor(short, TfidfIntentRouter.load(resolved))
        else:
            encoder = embedder()
            if encoder is None:
                skipped = "the ml extra (sentence-transformers) is not installed where evaluate ran"
                continue
            models[short] = RoutePredictor(short, EmbeddingIntentRouter.load(resolved, encoder))
        refs[short] = str(resolved.ref)
        metadata[short] = dict(resolved.metadata)
    return models, refs, metadata, skipped


def evaluate_all(
    store: FilesystemModelStore,
    tracker: Tracker,
    embedder: EmbedderFactory,
    *,
    alias: str = "candidate",
    corpus_dir: Path = CORPUS_DIR,
    report: Path | None = DOCS_EVALUATION_DIR / "router.md",
    warehouse: Path | None = None,
    artifacts: Path = ARTIFACTS_DIR,
) -> dict[str, Any]:
    dataset = build_dataset(corpus_dir)
    learned, refs, metadata, skipped = _load_learned(store, alias, embedder)
    if "tfidf" not in learned:
        raise ModelArtifactNotFoundError(f"no router:tfidf@{alias}; run bank-ml router train first")
    stale = [name for name, meta in metadata.items() if meta.get("dataset_hash") != dataset.content_hash]
    if stale:
        raise ValueError(f"the corpus changed since {', '.join(stale)} was trained; run bank-ml router train again")
    train_items, dev_items, test_items = dataset.split("train"), dataset.split("dev"), dataset.split("test")
    models: dict[str, RouterModel] = {"majority": MajorityBaseline(train_items), "keyword@1": keyword_baseline()}
    models.update(learned)
    result: dict[str, Any] = {
        "generated_at": generated_now().isoformat(),
        "git_sha": git_sha(),
        "alias": alias,
        "dataset": {
            "version": dataset.card.version,
            "hash": dataset.content_hash,
            "rows_per_split": dict(dataset.card.rows_per_split),
        },
        "artifacts": refs,
        "embeddings_skipped": skipped,
        "thresholds": {name: metadata[name]["threshold"] for name in learned},
        "models": {},
        "errors": {},
    }
    for name, model in models.items():
        scored = Scored(name, test_items, model.predict(test_items))
        evaluation = evaluate(scored)
        test = {**evaluation.pop("summary"), **evaluation}
        dev = summary(Scored(f"{name}:dev", dev_items, model.predict(dev_items)))
        result["models"][name] = {"test": test, "dev": dev}
        if name in learned:
            result["errors"][name] = errors(scored)
    lexicon = load_lexicon(corpus_dir)
    robust = [models["keyword@1"], *learned.values()]
    result["robustness"] = robustness(robust, test_items, lexicon)
    groups = {item.seed_id: item.split for item in dataset.items}
    held_out = [
        p for p in load_paraphrases("eval", dataset.seeds, lexicon, corpus_dir) if groups.get(p.seed_id) == "test"
    ]
    result["paraphrase_eval"] = (
        f"{len(held_out)} items (review pending)"
        if held_out
        else "pending: needs a language model provider (`bank-ml router paraphrase --purpose eval`); none generated"
    )
    c = float(metadata["tfidf"]["params"]["C"])
    result["transfer"] = transfer(learned["tfidf"], train_items, dev_items, test_items, c) | {
        "reference": refs["tfidf"]
    }
    result["language_detection"] = language_detection(dataset.items)
    result["transcripts"] = analyze(warehouse) if warehouse is not None else analyze()
    files = ValidationFiles.default(corpus_dir)
    result["validation"] = status(files)
    (artifacts / "evaluations").mkdir(parents=True, exist_ok=True)
    output = artifacts / "evaluations" / "router.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    if report is not None:
        from bank_ml.router.report import render

        report.write_text(render(result), encoding="utf-8")
    test_metrics = {
        f"test_{key}_{name.replace('@', '_v')}": result["models"][name]["test"][key]["estimate"]
        for name in models
        for key in ("accuracy", "macro_f1", "workflow_accuracy")
    }
    tracker.log_run(
        EXPERIMENT,
        f"evaluate {alias}",
        {"alias": alias, **refs},
        test_metrics,
        {"dataset_hash": dataset.content_hash, "git_sha": result["git_sha"]},
        {"evaluation": output},
    )
    return result


def export_validation(corpus_dir: Path = CORPUS_DIR) -> str:
    dataset = build_dataset(corpus_dir)
    return export(dataset.split("test"), ValidationFiles.default(corpus_dir))
