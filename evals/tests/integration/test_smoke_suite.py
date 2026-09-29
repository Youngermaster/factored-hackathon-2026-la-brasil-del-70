"""The 12-scenario smoke suite end to end: B0, P, and B1 with the scripted client, H as the reference loader, and
the CLI from run to published summaries that the API adapter reads."""

import asyncio
import json
from pathlib import Path

from typer.testing import CliRunner

from bank_agent.adapters.evaluation.summaries import FilesystemEvaluationSummaries
from bank_evals.cli import app
from bank_evals.runner.run import RunOptions, execute
from bank_evals.scenarios.model import Split
from bank_evals.systems.historical import load_historical

RUNNER = CliRunner()


def test_the_smoke_suite_runs_every_system_without_a_harness_error(tmp_path: Path) -> None:
    options = RunOptions(
        run_id="smoke-it",
        split=Split.DEV,
        llm="fake",
        smoke=True,
        out_dir=tmp_path,
        cassette_dir=tmp_path / "cassettes",
    )
    output = asyncio.run(execute(options))
    assert output.results_count == 36
    assert output.manifest["harness_errors"] == 0
    assert set(output.metrics) == {"b0", "p", "b1"}
    for data in output.metrics.values():
        assert data["aggregate"]["cases"] == 12
        assert {w for w, block in data["workflows"].items() if block["cases"] == 3} == {
            "account_inquiry",
            "card_support",
            "dispute",
            "credit",
        }
    assert output.manifest["systems"]["b1"].startswith("fake/scripted")
    references = load_historical()
    assert set(references) == {"account_inquiry", "card_support", "dispute", "credit"}
    assert all(0 < ref.first_contact_resolution <= 1 for ref in references.values())


def test_the_cli_runs_reports_compares_publishes_estimates_and_judges(tmp_path: Path) -> None:
    for run_id in ("cli-a", "cli-b"):
        done = RUNNER.invoke(
            app,
            [
                "run",
                "--run-id",
                run_id,
                "--split",
                "dev",
                "--smoke",
                "--llm",
                "fake",
                "--systems",
                "b0,p",
                "--out-dir",
                str(tmp_path),
            ],
        )
        assert done.exit_code == 0, done.output
        assert "p: safe automated resolution" in done.output
    run_dir = tmp_path / "cli-a"
    assert RUNNER.invoke(app, ["report", str(run_dir)]).exit_code == 0
    compared = RUNNER.invoke(app, ["compare", str(run_dir), str(tmp_path / "cli-b")])
    assert "| p | aggregate |" in compared.output
    summaries, docs = tmp_path / "summaries", tmp_path / "docs"
    published = RUNNER.invoke(
        app, ["publish", str(run_dir), "--summaries-dir", str(summaries), "--docs-dir", str(docs)]
    )
    assert published.exit_code == 0, published.output
    read = asyncio.run(FilesystemEvaluationSummaries(summaries).list())
    assert {s.system for s in read} == {"b0", "p"}
    assert (docs / "results.md").read_text(encoding="utf-8").startswith("# Evaluation results")
    assert (docs / "runs" / "cli-a" / "metrics.json").is_file()
    estimate = RUNNER.invoke(app, ["estimate", str(run_dir)])
    assert estimate.exit_code == 0
    assert "total_calls" in estimate.output
    judged = RUNNER.invoke(app, ["judge", str(run_dir), "--sample", "5"])
    assert judged.exit_code == 0, judged.output
    assert json.loads((run_dir / "judge_agreement.json").read_text(encoding="utf-8"))["status"] == "pending"
    rated = RUNNER.invoke(app, ["judge", str(run_dir), "--ratings", str(run_dir / "judge_sample.jsonl")])
    assert rated.exit_code == 0


def test_publish_refuses_a_run_with_harness_errors_unless_allowed(tmp_path: Path) -> None:
    RUNNER.invoke(
        app, ["run", "--run-id", "partial", "--smoke", "--llm", "fake", "--systems", "p", "--out-dir", str(tmp_path)]
    )
    manifest_path = tmp_path / "partial" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_path.write_text(json.dumps({**manifest, "harness_errors": 1}), encoding="utf-8")
    args = [
        "publish",
        str(tmp_path / "partial"),
        "--summaries-dir",
        str(tmp_path / "s"),
        "--docs-dir",
        str(tmp_path / "d"),
    ]
    assert RUNNER.invoke(app, args).exit_code == 2
    assert RUNNER.invoke(app, [*args, "--allow-partial"]).exit_code == 0


def test_the_scenario_commands_check_the_committed_set_and_protect_the_lock(tmp_path: Path) -> None:
    checked = RUNNER.invoke(app, ["scenarios", "check"])
    assert checked.exit_code == 0, checked.output
    first = RUNNER.invoke(app, ["scenarios", "generate", "--out-dir", str(tmp_path)])
    assert first.exit_code == 0
    assert (tmp_path / "test_set.lock").is_file()
    (tmp_path / "scenarios.test.jsonl").write_text("{}\n", encoding="utf-8")
    assert RUNNER.invoke(app, ["scenarios", "generate", "--out-dir", str(tmp_path)]).exit_code == 1
    assert RUNNER.invoke(app, ["scenarios", "generate", "--out-dir", str(tmp_path), "--relock"]).exit_code == 0


def test_a_test_split_run_checks_the_lock_and_repeats_the_subset(tmp_path: Path) -> None:
    options = RunOptions(
        run_id="test-it",
        split=Split.TEST,
        systems=("b0",),
        runs=2,
        llm="off",
        out_dir=tmp_path,
        scenario_ids=("test-car-normal-001", "test-car-tool-fai-001"),
    )
    output = asyncio.run(execute(options))
    assert output.manifest["test_set_lock"] is not None
    assert output.results_count == 4
    assert output.metrics["b0"]["repeated"]["runs"] == 2
