"""Retrieval evaluation on the committed starter judgments, end to end, over the real policy pack.

Dense and hybrid run on the deterministic fake embedder here (fixture), so the test needs no model download;
``make eval-retrieval`` runs them on the real model when the optional ml extra is installed.
"""

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from bank_agent.bootstrap.settings import DEFAULT_POLICY_DIR
from bank_agent_retrieval import HashingEmbedder
from bank_evals.cli import app
from bank_evals.retrieval.command import run_retrieval_evaluation
from bank_evals.retrieval.judgments import DEFAULT_JUDGMENTS, load_judgments
from bank_evals.retrieval.tracking import MlflowTracker


def test_the_starter_judgments_cover_every_workflow_locale_and_split() -> None:
    judgments = load_judgments(DEFAULT_JUDGMENTS)
    assert len(judgments) == 100
    assert Counter(j.workflow for j in judgments) == {
        "account_inquiry": 20,
        "card_support": 20,
        "dispute": 20,
        "credit": 20,
        "out_of_scope": 20,
    }
    assert Counter(j.split for j in judgments) == {"dev": 40, "test": 60}
    for workflow in {j.workflow for j in judgments}:
        assert {j.locale.value for j in judgments if j.workflow == workflow} == {"es-MX", "es-CO", "es-AR", "pt-BR"}
    assert {j.provenance for j in judgments} == {"team_generated"}
    assert {j.review_status for j in judgments} == {"pending"}


def test_the_evaluation_runs_end_to_end_and_logs_to_mlflow(tmp_path: Path) -> None:
    output = tmp_path / "retrieval.md"
    run = run_retrieval_evaluation(
        judgments_path=DEFAULT_JUDGMENTS,
        policy_dir=DEFAULT_POLICY_DIR,
        output=output,
        tracker=MlflowTracker(f"file:{tmp_path / 'mlruns'}"),
        generated_at=datetime(2026, 9, 27, tzinfo=UTC),
        git_sha="fixture",
        embedder=HashingEmbedder(),
        embedder_kind="fixture hashing embedder",
    )
    names = [report.name for report in run.evaluation.reports]
    assert names == ["bm25", "dense", "hybrid"]
    bm25 = run.evaluation.reports[0]
    assert (bm25.test.n_in_scope, bm25.test.n_out_of_scope) == (48, 12)
    assert bm25.test.recall_at_5 is not None
    assert bm25.test.recall_at_5 >= 0.8
    assert run.evaluation.document_count == 123
    assert output.read_text(encoding="utf-8") == run.report
    assert "fixture hashing embedder" in run.report
    assert run.run_id is not None
    assert list((tmp_path / "mlruns").rglob("bm25.test.recall_at_1"))


def test_the_command_writes_the_report_without_dense_or_mlflow(tmp_path: Path) -> None:
    output = tmp_path / "report.md"
    result = CliRunner().invoke(app, ["retrieval", "--no-dense", "--no-mlflow", "--output", str(output)])
    assert result.exit_code == 0, result.output
    assert "bm25: threshold" in result.output
    # The committed recording of hosted embeddings makes the Qdrant rows run offline by default.
    assert "qdrant_hybrid: threshold" in result.output
    assert "## Production decision (pre-registered rule)" in output.read_text(encoding="utf-8")
    assert "not run: the optional ml extra is not installed or --no-dense was given" in output.read_text(
        encoding="utf-8"
    )
    broken = tmp_path / "broken.jsonl"
    broken.write_text("{}\n", encoding="utf-8")
    refused = CliRunner().invoke(app, ["retrieval", "--no-dense", "--no-mlflow", "--judgments", str(broken)])
    assert refused.exit_code == 2
