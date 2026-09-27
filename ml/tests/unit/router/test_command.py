"""``bank-ml router``: argument handling and messages, with the pipeline stubbed (no real registry or corpus writes)."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from bank_agent.adapters.llm.unconfigured import UnconfiguredLLMClient
from bank_agent.adapters.models.registry import FilesystemModelStore
from bank_ml.cli import app
from bank_ml.router import command

runner = CliRunner()


def test_router_commands_are_listed() -> None:
    result = runner.invoke(app, ["router", "--help"])
    assert result.exit_code == 0
    for name in ("train", "evaluate", "promote", "paraphrase", "export-validation"):
        assert name in result.output


def test_train_and_evaluate_report_what_they_did(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dataset = SimpleNamespace(content_hash="a" * 64, card=SimpleNamespace(rows_per_split={"train": 1}))
    trained = SimpleNamespace(dataset=dataset, registered={"tfidf": "router:tfidf@abc"}, skipped={"embeddings": "x"})
    monkeypatch.setattr(command, "train", lambda *args, **kwargs: trained)
    result = runner.invoke(app, ["router", "train", "--registry-dir", str(tmp_path), "--tracking-uri", "none"])
    assert result.exit_code == 0, result.output
    assert "router:tfidf@abc" in result.output
    assert "skipped embeddings" in result.output
    seen: dict[str, Any] = {}

    def fake_evaluate(*args: object, **kwargs: object) -> dict[str, Any]:
        seen.update(kwargs)
        score = {"estimate": 0.5}
        return {"models": {"tfidf": {"test": {"accuracy": score, "macro_f1": score}}}}

    monkeypatch.setattr(command, "evaluate_all", fake_evaluate)
    result = runner.invoke(app, ["router", "evaluate", "--registry-dir", str(tmp_path), "--no-report"])
    assert result.exit_code == 0, result.output
    assert "tfidf: accuracy 0.500" in result.output
    assert seen["report"] is None


def test_promote_without_a_candidate_says_so(tmp_path: Path) -> None:
    result = runner.invoke(app, ["router", "promote", "--approved-by", "reviewer", "--registry-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "router:tfidf: no candidate" in result.output
    assert "router:embeddings: no candidate" in result.output


def test_promote_records_a_refusal(tmp_path: Path) -> None:
    store = FilesystemModelStore(tmp_path)
    resolved = store.register("router:tfidf", {"format": "x"}, {"metrics": {}, "baseline_metrics": {}})
    store.set_alias("router:tfidf", "candidate", resolved.ref.version, {})
    args = ["router", "promote", "--approved-by", "reviewer", "--registry-dir", str(tmp_path), "--model", "tfidf"]
    result = runner.invoke(app, args)
    assert "router:tfidf: refused (metrics missing" in result.output


def test_paraphrase_without_a_provider_stops_and_writes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(command, "build_client", UnconfiguredLLMClient)
    result = runner.invoke(app, ["router", "paraphrase", "--purpose", "eval"])
    assert result.exit_code == 1
    assert "no cassette created" in result.output
    assert runner.invoke(app, ["router", "paraphrase", "--purpose", "other"]).exit_code != 0


def test_export_validation_reports_the_outcome(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(command, "export_validation", lambda: "kept")
    result = runner.invoke(app, ["router", "export-validation"])
    assert result.output.strip() == "validation sheet: kept"
