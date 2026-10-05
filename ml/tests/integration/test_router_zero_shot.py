"""The hosted model router benchmark end to end on a small fixture corpus: TF-IDF trained and registered, the model
replies replayed from a deterministic fake (no cassette and no live model), every system scored, the decision
applied on dev, and the report rendered with the hand-written decision kept across a regeneration."""

import hashlib
import json
import shutil
from collections.abc import Sequence
from pathlib import Path

import pytest
import yaml

from bank_agent.adapters.models.registry import FilesystemModelStore
from bank_agent.domain.workflow import Intent
from bank_ml.common.tracking import NullTracker
from bank_ml.router.augment import Item
from bank_ml.router.corpus import CORPUS_DIR
from bank_ml.router.dataset import build_dataset
from bank_ml.router.pipeline import train
from bank_ml.router.zero_shot import LlmPrediction
from bank_ml.router.zero_shot_report import DECISION_BEGIN, DECISION_END, benchmark, render, write_benchmark

PER_LOCALE = 3
MODELS = ("azure/gpt-4.1-mini",)


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


def _fake_replay(models: Sequence[str], items: Sequence[Item], _: Path) -> dict[str, list[LlmPrediction]]:
    """Right with confidence 0.95 for three items in four, wrong with 0.6 otherwise, one failure per model."""
    replies: dict[str, list[LlmPrediction]] = {}
    for position, model in enumerate(models):
        rows = []
        for number, item in enumerate(items):
            bucket = int(hashlib.sha256(f"{model}{item.item_id}".encode()).hexdigest()[:4], 16) % 4
            if number == position:
                rows.append(LlmPrediction(item.item_id, Intent.UNSUPPORTED, 0.0, (), 0, 0, 0, error="llm_timeout"))
            elif bucket:
                rows.append(LlmPrediction(item.item_id, item.intent, 0.95, (item.intent.value,), 900, 950, 30))
            else:
                wrong = Intent.CARD_BLOCK if item.intent is not Intent.CARD_BLOCK else Intent.CARD_STATUS
                rows.append(LlmPrediction(item.item_id, wrong, 0.6, (wrong.value,), 1100, 950, 30))
        replies[model] = rows
    return replies


@pytest.fixture(scope="module")
def registered(corpus: Path, tmp_path_factory: pytest.TempPathFactory) -> tuple[FilesystemModelStore, str]:
    root = tmp_path_factory.mktemp("trained")
    store = FilesystemModelStore(root / "registry")
    trained = train(store, NullTracker(), lambda: None, corpus_dir=corpus, artifacts=root / "artifacts")
    return store, trained.registered["tfidf"].split("@")[1]


def test_benchmark_scores_every_system_and_renders_the_report(
    corpus: Path, registered: tuple[FilesystemModelStore, str], tmp_path: Path
) -> None:
    store, version = registered
    dataset = build_dataset(corpus)
    result = benchmark(dataset, MODELS, store, version, tmp_path / "cassettes", replay=_fake_replay)

    tfidf = f"tfidf@{version}"
    expected = {
        "keyword@1",
        tfidf,
        *(f"zero-shot {model}" for model in MODELS),
        *(f"{base} then {model}" for base in (tfidf, "keyword@1") for model in MODELS),
    }
    assert set(result["systems"]) == expected
    zero_shot = result["systems"]["zero-shot azure/gpt-4.1-mini"]["test"]
    assert zero_shot["usage"]["model_share"] == 1.0
    assert zero_shot["usage"]["cost_usd_per_1000"] is not None
    assert result["systems"][tfidf]["test"]["usage"]["cost_usd_per_1000"] == "0"
    cascade = result["systems"][f"{tfidf} then azure/gpt-4.1-mini"]["test"]["usage"]
    assert 0.0 <= cascade["model_share"] <= 1.0
    assert set(result["decision"]["candidates"]) == set(MODELS)
    assert set(result["thresholds"]) >= {f"zero-shot {model}" for model in MODELS}
    assert set(result["regions"]["tfidf"]) == {"acts", "abstains"}
    assert set(zero_shot["workflow_confusion_by_language"]) == {"es", "pt"}
    json.dumps(result, default=str)

    report = render(result)
    for heading in (
        "## Pre-registered decision rule",
        "## Dev: the rule applied",
        "## Test split (held out; report only)",
        "## Where the model helps",
        "## Calibration of the stated confidence (test)",
        "## Label audit candidates (test)",
        "## Decision",
    ):
        assert heading in report
    assert "\u2014" not in report  # no em dash in generated copy
    assert f"`keyword@1 then {MODELS[0]}`" in report

    output = tmp_path / "router-llm.md"
    output.write_text(f"old\n{DECISION_BEGIN}\nKeep keyword@1 in production.\n{DECISION_END}\n", encoding="utf-8")
    write_benchmark(
        dataset,
        MODELS,
        store,
        version,
        tmp_path / "cassettes",
        output,
        evaluations_dir=tmp_path / "evaluations",
        replay=_fake_replay,
    )
    assert "Keep keyword@1 in production." in output.read_text(encoding="utf-8")
    assert (tmp_path / "evaluations" / "router_llm.json").is_file()


def test_benchmark_refuses_a_model_trained_on_another_corpus(
    registered: tuple[FilesystemModelStore, str], tmp_path: Path
) -> None:
    store, version = registered
    with pytest.raises(ValueError, match="another corpus"):
        benchmark(build_dataset(), MODELS, store, version, tmp_path / "cassettes", replay=_fake_replay)
