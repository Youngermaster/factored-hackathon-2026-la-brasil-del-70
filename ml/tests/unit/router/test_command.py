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


def test_zero_shot_records_one_model_and_reports_from_the_cassettes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert "zero-shot" in runner.invoke(app, ["router", "--help"]).output
    dataset = SimpleNamespace(split=lambda name: [SimpleNamespace(item_id=f"{name}{n}") for n in range(3)])
    monkeypatch.setattr(command, "build_dataset", lambda: dataset)
    seen: dict[str, Any] = {}

    async def fake_classify(model: str, items: list[Any], cassette_dir: Path, **kwargs: Any) -> SimpleNamespace:
        seen.update(model=model, items=len(items), **kwargs)
        return SimpleNamespace(predictions=[SimpleNamespace(failed=False)] * len(items), recorded=len(items))

    monkeypatch.setattr(command, "classify_items", fake_classify)
    args = ["router", "zero-shot", "--model", "azure/m", "--record", "--limit", "2", "--no-report"]
    result = runner.invoke(app, [*args, "--cassette-dir", str(tmp_path), "--per-minute", "30"])
    assert result.exit_code == 0, result.output
    assert "azure/m: 4 items, 4 recorded now, 0 failed" in result.output
    assert (seen["model"], seen["items"], seen["record"], seen["per_minute"]) == ("azure/m", 4, True, 30.0)

    two = runner.invoke(app, ["router", "zero-shot", "--model", "a/x", "--model", "b/y", "--record"])
    assert two.exit_code != 0
    assert "one model at a time" in two.output
    partial = runner.invoke(app, ["router", "zero-shot", "--split", "dev"])
    assert partial.exit_code != 0
    assert "every item of dev and test" in partial.output
    unknown = runner.invoke(app, ["router", "zero-shot", "--split", "train"])
    assert unknown.exit_code != 0

    usage = {"cost_usd_per_1000": "0.4100"}
    score = {"estimate": 0.5}
    systems = {"zero-shot azure/m": {"test": {"accuracy": score, "macro_f1": score, "usage": usage}}}
    monkeypatch.setattr(command, "write_benchmark", lambda *args, **kwargs: {"systems": systems})
    reported = runner.invoke(app, ["router", "zero-shot", "--model", "azure/m"])
    assert reported.exit_code == 0, reported.output
    assert "zero-shot azure/m: accuracy 0.500, macro-F1 0.500, cost per 1,000 0.4100 USD" in reported.output
