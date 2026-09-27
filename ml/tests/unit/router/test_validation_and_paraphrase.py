"""The human validation sheet and agreement, the paraphrase generator (scripted ``FakeLLM``, never a live model or
a fabricated cassette), and the transcript analysis without a warehouse."""

import csv
import json
from pathlib import Path

import pytest

from bank_agent.domain.errors import LlmInvalidOutputError, LlmProviderRejectedError
from bank_agent.domain.workflow import Intent
from bank_agent.testing.fake_llm import FakeLLM, ScriptedError, ScriptedResponse
from bank_ml.router.augment import Item
from bank_ml.router.corpus import Seed, load_lexicon
from bank_ml.router.dataset import build_dataset
from bank_ml.router.paraphrase import PROMPTS, generate, load_paraphrases, paraphrase_file
from bank_ml.router.transcripts import analyze, contact_reason_mapping
from bank_ml.router.validation import SAMPLE_SIZE, ValidationFiles, cohen_kappa, export, sample, status

SEED = Seed("card_block:es-MX:01", Intent.CARD_BLOCK, "es-MX", "Quiero bloquear mi tarjeta {last4}")


def _files(tmp_path: Path) -> ValidationFiles:
    return ValidationFiles(tmp_path / "sheet.csv", tmp_path / "sheet.key.csv")


def test_the_sample_is_stratified_blind_and_kept_once_labeled(tmp_path: Path) -> None:
    test = build_dataset().split("test")
    chosen = sample(test)
    assert len(chosen) == SAMPLE_SIZE
    assert len({(item.intent, item.locale) for item in chosen}) == 17 * 4
    files = _files(tmp_path)
    assert status(files) == {"status": "not exported"}
    assert export(test, files) == "written"
    header = files.sheet.read_text().splitlines()[0]
    assert "intent" not in header.replace("labeler_1_intent", "").replace("labeler_2_intent", "").replace(
        "adjudicated_intent", ""
    )
    assert status(files) == {"status": "pending", "items": SAMPLE_SIZE}
    with files.sheet.open() as stream:
        rows = list(csv.DictReader(stream))
    with files.key.open() as stream:
        key = {row["item_id"]: row["assigned_intent"] for row in csv.DictReader(stream)}
    for row in rows[:10]:
        row.update(labeler_1_intent=key[row["item_id"]], labeler_2_intent=key[row["item_id"]])
        row["adjudicated_intent"] = key[row["item_id"]]
    rows[0]["adjudicated_intent"] = "unsupported" if key[rows[0]["item_id"]] != "unsupported" else "card_block"
    with files.sheet.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    assert export(test, files) == "kept"
    result = status(files)
    assert (result["double_labeled"], result["adjudicated"], result["label_accuracy"]) == (10, 10, 0.9)


def test_cohen_kappa() -> None:
    assert cohen_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    assert cohen_kappa(["a", "a"], ["a", "a"]) == 1.0
    assert cohen_kappa([], []) == 0.0
    assert cohen_kappa(["a", "b", "a", "b"], ["b", "a", "b", "a"]) == pytest.approx(-1.0)


async def test_paraphrases_are_written_with_provenance_and_loaded_as_items(tmp_path: Path) -> None:
    fake = FakeLLM()
    fake.script(
        PROMPTS["train"],
        ScriptedResponse({"paraphrases": ["Bloqueen mi tarjeta {last4} ya", "quiero bloquear mi tarjeta {last4}"]}),
    )
    result = await generate(fake, [SEED], "train", corpus_dir=tmp_path)
    assert (result.written, result.failed, result.stopped) == (1, 0, None)
    row = json.loads(paraphrase_file("train", tmp_path).read_text())
    assert row["provenance"] == "llm_paraphrased:card_block:es-MX:01"
    assert row["review_status"] == "pending"
    assert fake.calls[0].variables["locale"] == "es-MX"
    items = load_paraphrases("train", [SEED], load_lexicon(), corpus_dir=tmp_path)
    assert [item.text for item in items] == ["Bloqueen mi tarjeta 4821 ya"]
    assert items[0].augmentation == "paraphrase_train"
    assert load_paraphrases("eval", [SEED], load_lexicon(), corpus_dir=tmp_path) == []


async def test_generation_stops_without_a_provider_and_counts_invalid_outputs(tmp_path: Path) -> None:
    refused = FakeLLM()
    refused.script(PROMPTS["eval"], ScriptedError(LlmProviderRejectedError))
    stopped = await generate(refused, [SEED], "eval", corpus_dir=tmp_path)
    assert stopped.stopped is not None
    assert stopped.path is None
    assert not paraphrase_file("eval", tmp_path).exists()
    invalid = FakeLLM()
    invalid.script(PROMPTS["eval"], ScriptedError(LlmInvalidOutputError))
    counted = await generate(invalid, [SEED], "eval", corpus_dir=tmp_path)
    assert (counted.written, counted.failed) == (0, 1)


def test_paraphrases_with_unknown_slots_or_seeds_are_ignored(tmp_path: Path) -> None:
    path = paraphrase_file("train", tmp_path)
    path.parent.mkdir(parents=True)
    rows = [
        {"seed_id": SEED.seed_id, "text": "bloquear {bogus}", "prompt": str(PROMPTS["train"]), "provenance": "x"},
        {"seed_id": "missing:es-MX:01", "text": "hola", "prompt": str(PROMPTS["train"]), "provenance": "x"},
        {"seed_id": SEED.seed_id, "text": "bloquear", "prompt": str(PROMPTS["eval"]), "provenance": "x"},
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    assert load_paraphrases("train", [SEED], load_lexicon(), corpus_dir=tmp_path) == []


def test_transcript_analysis_needs_a_warehouse(tmp_path: Path) -> None:
    assert analyze(tmp_path / "absent.duckdb") is None
    mapping = contact_reason_mapping()
    assert mapping["Transaccional"] == "account_inquiry"
    assert mapping["Queja"] == "dispute"


def test_items_know_their_language() -> None:
    item = Item("i", "s", Intent.CARD_BLOCK, "pt-BR", "oi", "team_authored", "canonical")
    assert item.language == "pt"
    assert item.with_split("g", "test").split == "test"
