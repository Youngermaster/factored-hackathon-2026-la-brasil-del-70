"""The router end to end on a small fixture corpus (three seeds per intent and locale, cut from the committed
corpus): train with MLflow tracking, evaluate, promote, load through the ``bank_agent`` composition root, predict,
and retrain for reproducibility. The embedding router uses a deterministic hashing embedder (a test fixture)."""

import hashlib
import math
import shutil
from collections.abc import Sequence
from pathlib import Path

import pytest
import yaml

from bank_agent.adapters.models.registry import FilesystemModelStore
from bank_agent.adapters.models.tfidf_router import TfidfIntentRouter
from bank_agent.adapters.retrieval.embedding import Vector
from bank_agent.bootstrap.models import build_model_registry, build_router
from bank_agent.bootstrap.settings import WorkflowSettings
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.locale import Language
from bank_ml.common.promotion import promote
from bank_ml.common.reports import generated_now
from bank_ml.common.tracking import MlflowTracker, NullTracker
from bank_ml.router.command import RULE
from bank_ml.router.corpus import CORPUS_DIR
from bank_ml.router.pipeline import evaluate_all, export_validation, train

PER_LOCALE = 3


class HashingEmbedder:
    """Character trigrams hashed into 64 dimensions and normalized: deterministic, offline, test only."""

    model_id = "fixture-hashing-embedder"

    def embed_passages(self, texts: Sequence[str]) -> list[Vector]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> Vector:
        vector = [0.0] * 64
        padded = f"  {text.lower()}  "
        for start in range(len(padded) - 2):
            vector[int(hashlib.sha256(padded[start : start + 3].encode()).hexdigest()[:8], 16) % 64] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return tuple(value / norm for value in vector)


@pytest.fixture(scope="module")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("corpus")
    (root / "seeds").mkdir()
    shutil.copy(CORPUS_DIR / "lexicon.yaml", root / "lexicon.yaml")
    for path in sorted((CORPUS_DIR / "seeds").glob("*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        document["seeds"] = {locale: seeds[:PER_LOCALE] for locale, seeds in document["seeds"].items()}
        (root / "seeds" / path.name).write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")
    return root


def test_train_evaluate_promote_and_serve(corpus: Path, tmp_path: Path) -> None:
    store = FilesystemModelStore(tmp_path / "registry")
    # The file store: MLflow's SQLite store emits a SQLAlchemy 2.1 deprecation warning inside MLflow, and this suite
    # treats warnings as errors. `make train` exercises the SQLite default.
    tracker = MlflowTracker((tmp_path / "mlruns").as_uri())
    result = train(store, tracker, HashingEmbedder, corpus_dir=corpus, artifacts=tmp_path / "artifacts")
    assert set(result.registered) == {"tfidf", "embeddings"}
    candidate = store.registry.resolve("router:tfidf", "candidate")
    assert candidate.metadata["dataset_hash"] == result.dataset.content_hash
    assert candidate.metadata["mlflow_run_id"]
    assert (tmp_path / "artifacts" / "datasets" / "router").is_dir()

    report = tmp_path / "router.md"
    evaluation = evaluate_all(
        store,
        NullTracker(),
        HashingEmbedder,
        corpus_dir=corpus,
        report=report,
        warehouse=tmp_path / "absent.duckdb",
        artifacts=tmp_path / "artifacts",
    )
    assert set(evaluation["models"]) == {"majority", "keyword@1", "tfidf", "embeddings"}
    assert evaluation["validation"] == {"status": "not exported"}
    assert export_validation(corpus) == "written"
    assert (corpus / "validation" / "router_validation_v1.key.csv").is_file()
    assert evaluation["transcripts"] is None
    text = report.read_text()
    assert "## Test split (held out)" in text
    assert "xychart-beta" in text
    assert (tmp_path / "artifacts" / "evaluations" / "router.json").is_file()

    decision = promote(store, "router:tfidf", RULE, approved_by="integration test", now=generated_now(), commit="test")
    history = store.history("router:tfidf")
    assert history[-1]["decision"] == ("promoted" if decision.promote else "refused")
    assert history[-1]["compared_with"] == "router:keyword@1"
    assert set(history[-1]["metrics_compared"]) == {
        "dev_macro_f1",
        "dev_high_stakes_recall_mean",
        "dev_workflow_accuracy",
    }
    if not decision.promote:  # a tiny fixture corpus may not beat the baseline; serve it anyway for this check
        store.set_alias("router:tfidf", "champion", candidate.ref.version, {"approved_by": "integration test"})
    settings = WorkflowSettings(_env_file=None, router="tfidf@champion", model_registry_dir=tmp_path / "registry")
    router = build_router(settings, build_model_registry(tmp_path / "registry"))
    assert isinstance(router, TfidfIntentRouter)
    prediction = router.route(UntrustedText("Quiero bloquear mi tarjeta, me la robaron"), Language.ES)
    assert str(prediction.model) == str(candidate.ref)


def test_retraining_reproduces_the_artifacts_and_metrics(corpus: Path, tmp_path: Path) -> None:
    runs = []
    for attempt in ("first", "second"):
        store = FilesystemModelStore(tmp_path / attempt)
        train(store, NullTracker(), lambda: None, corpus_dir=corpus, artifacts=tmp_path / f"{attempt}-artifacts")
        runs.append(store.registry.resolve("router:tfidf", "candidate"))
    first, second = runs
    assert first.ref == second.ref
    assert first.sha256 == second.sha256
    for metric, value in first.metadata["metrics"].items():  # type: ignore[union-attr]
        assert second.metadata["metrics"][metric] == pytest.approx(value, abs=1e-9)  # type: ignore[index]


def test_evaluate_refuses_a_missing_or_stale_model(corpus: Path, tmp_path: Path) -> None:
    store = FilesystemModelStore(tmp_path / "registry")
    with pytest.raises(Exception, match="router train"):
        evaluate_all(store, NullTracker(), lambda: None, corpus_dir=corpus, report=None, artifacts=tmp_path)
    train(store, NullTracker(), lambda: None, corpus_dir=corpus, artifacts=tmp_path)
    seed_file = corpus / "seeds" / "greeting_or_other.yaml"
    original = seed_file.read_text(encoding="utf-8")
    try:
        seed_file.write_text(original.replace("seeds:", "seeds:", 1) + "\n# changed\n", encoding="utf-8")
        document = yaml.safe_load(original)
        document["seeds"]["es-MX"][0] = "Hola, muy buenas tardes a todos ustedes"
        seed_file.write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")
        with pytest.raises(ValueError, match="corpus changed"):
            evaluate_all(store, NullTracker(), lambda: None, corpus_dir=corpus, report=None, artifacts=tmp_path)
    finally:
        seed_file.write_text(original, encoding="utf-8")
