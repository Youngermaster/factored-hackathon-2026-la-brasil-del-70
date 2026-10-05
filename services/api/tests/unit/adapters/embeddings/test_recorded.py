"""Recorded embeddings: record with an inner embedder, replay offline, and refuse what was never recorded."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bank_agent.adapters.embeddings.recorded import (
    RECORD_COMMAND,
    RecordedEmbedder,
    decode_vector,
    encode_vector,
    record_key,
)
from bank_agent.domain.errors import EmbeddingRejectedError
from bank_agent_retrieval import HashingEmbedder

WHEN = datetime(2026, 10, 5, 16, 0, tzinfo=UTC)
PASSAGES = ["[fixture] bloqueo preventivo de la tarjeta", "[fixture] plazo para aclarar un cargo"]


def recorded_file(tmp_path: Path) -> tuple[Path, HashingEmbedder]:
    inner = HashingEmbedder()
    path = tmp_path / "embeddings.jsonl"
    recorder = RecordedEmbedder(path, model_id=inner.model_id, inner=inner)
    recorder.embed_passages(PASSAGES)
    recorder.embed_query("[fixture] me robaron la tarjeta")
    recorder.save(recorded_at=WHEN, source="fixture")
    return path, inner


def test_replays_what_was_recorded_without_calling_a_model(tmp_path: Path) -> None:
    path, inner = recorded_file(tmp_path)
    replay = RecordedEmbedder.replay(path)
    assert replay.model_id == inner.model_id
    assert (replay.dimension, len(replay), replay.recorded_at) == (64, 3, WHEN.isoformat())
    expected = inner.embed_passages(PASSAGES)
    for got, want in zip(replay.embed_passages(PASSAGES), expected, strict=True):
        assert got == pytest.approx(want, abs=1e-6)
    assert replay.embed_query("[fixture] me robaron la tarjeta") == pytest.approx(
        inner.embed_query("[fixture] me robaron la tarjeta"), abs=1e-6
    )
    assert (replay.hits, replay.misses) == (3, 0)


def test_a_text_that_was_never_recorded_names_the_regeneration_command(tmp_path: Path) -> None:
    path, _ = recorded_file(tmp_path)
    replay = RecordedEmbedder.replay(path)
    with pytest.raises(EmbeddingRejectedError, match=RECORD_COMMAND):
        replay.embed_query("[fixture] otra pregunta")
    # A passage and a query with the same text are different records.
    with pytest.raises(EmbeddingRejectedError):
        replay.embed_query(PASSAGES[0])
    with pytest.raises(EmbeddingRejectedError, match="no recorded embeddings"):
        RecordedEmbedder.replay(tmp_path / "missing.jsonl")


def test_the_file_holds_hashes_not_text_sorted_for_clean_diffs(tmp_path: Path) -> None:
    path, _ = recorded_file(tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "tarjeta" not in text
    lines = [json.loads(line) for line in text.splitlines()]
    assert lines[0] == {
        "dimension": 64,
        "format": 1,
        "model_id": "fixture/hashing|q|p",
        "recorded_at": WHEN.isoformat(),
        "source": "fixture",
    }
    keys = [(item["kind"], item["key"]) for item in lines[1:]]
    assert keys == sorted(keys)
    assert ("query", record_key("query", "[fixture] me robaron la tarjeta")) in keys


def test_records_only_the_missing_texts_and_refuses_another_model(tmp_path: Path) -> None:
    path, _ = recorded_file(tmp_path)
    inner = HashingEmbedder()
    again = RecordedEmbedder(path, model_id=inner.model_id, inner=inner)
    again.embed_passages([*PASSAGES, "[fixture] saldo de la cuenta"])
    assert (again.hits, again.misses, inner.passage_calls) == (2, 1, 1)
    with pytest.raises(EmbeddingRejectedError, match="another model"):
        RecordedEmbedder(path, model_id="other/model|8")
    with pytest.raises(EmbeddingRejectedError, match="differs"):
        RecordedEmbedder(path, model_id="other/model|8", inner=inner)
    with pytest.raises(EmbeddingRejectedError, match="nothing to record"):
        RecordedEmbedder(tmp_path / "empty.jsonl", model_id=inner.model_id).save(recorded_at=WHEN, source="x")


def test_vectors_round_trip_as_float32_and_refuse_another_dimension() -> None:
    encoded = encode_vector((0.6, 0.8))
    assert decode_vector(encoded, 2) == pytest.approx((0.6, 0.8), abs=1e-7)
    with pytest.raises(EmbeddingRejectedError, match="dimension"):
        decode_vector(encoded, 3)
