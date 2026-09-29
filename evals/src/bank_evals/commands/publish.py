"""``bank-eval publish`` and ``bank-eval estimate``."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

import typer

from bank_agent.adapters.llm.prices import PriceTable
from bank_agent.bootstrap.settings import DEFAULT_EVAL_SUMMARIES_DIR, LLMSettings
from bank_agent.domain.evaluation import GitSha
from bank_evals.commands.run import load_run
from bank_evals.meta import REPOSITORY_ROOT
from bank_evals.reports.markdown import render_failures, render_report
from bank_evals.reports.summary import build_summary
from bank_evals.runner.estimate import estimate_run

DOCS_DIR = REPOSITORY_ROOT / "docs" / "evaluation"


def summary_notes(manifest: dict[str, Any], system: str) -> list[str]:
    misses = sum(manifest.get("cassette_misses", {}).values())
    return [
        f"Model and provider: {manifest['systems'][system]}.",
        f"{manifest['split']} split, {manifest['scenarios']} scenarios, scenario set SHA-256 "
        f"{manifest['scenario_set_hash'][:16]}; {manifest['runs']} run(s); language model mode {manifest['llm_mode']}.",
        f"Cassette misses: {misses}; harness errors: {manifest.get('harness_errors', 0)}.",
        "The aggregate sums the four workflows; the routing scenarios are reported in the results document.",
        "Latency is per turn, in process; cost uses the dated price table.",
        *([f"Commit {manifest['git_sha']} had uncommitted changes."] if "dirty" in manifest["git_sha"] else []),
    ]


def publish(
    run_dir: Annotated[Path, typer.Argument(help="reports/eval/<run_id>")],
    summaries_dir: Annotated[Path, typer.Option("--summaries-dir")] = DEFAULT_EVAL_SUMMARIES_DIR,
    docs_dir: Annotated[Path, typer.Option("--docs-dir")] = DOCS_DIR,
    allow_partial: Annotated[bool, typer.Option("--allow-partial", help="Publish despite misses or errors.")] = False,
    title: Annotated[str, typer.Option("--title", help="The heading of results.md and failures.md.")] = "",
) -> None:
    """Write the summaries the evaluation view reads, and results.md, failures.md, and the run's metrics."""
    manifest, metrics, results = load_run(run_dir)
    problems = sum(manifest.get("cassette_misses", {}).values()) + int(manifest.get("harness_errors", 0))
    if problems and not allow_partial:
        typer.echo(f"{problems} cassette misses or harness errors; rerun, or publish with --allow-partial", err=True)
        raise typer.Exit(2)
    run_id = manifest["run_id"]
    target = docs_dir / "runs" / run_id
    target.mkdir(parents=True, exist_ok=True)
    for name in ("metrics.json", "manifest.json"):
        shutil.copyfile(run_dir / name, target / name)
    heading = title or "Evaluation results"
    (docs_dir / "results.md").write_text(render_report(manifest, metrics, results, heading), encoding="utf-8")
    failures = render_failures(manifest, results, title=f"{heading}: failures" if title else "Evaluation failures")
    (docs_dir / "failures.md").write_text(failures, encoding="utf-8")
    summaries_dir.mkdir(parents=True, exist_ok=True)
    table = (
        str((docs_dir / "failures.md").relative_to(REPOSITORY_ROOT))
        if docs_dir.is_relative_to(REPOSITORY_ROOT)
        else None
    )
    sha: GitSha = manifest["git_sha"].split("-")[0] if manifest["git_sha"] != "unknown" else "0000000"
    dataset = f"{manifest['world']}:{manifest['split']}:{manifest['scenario_set_hash'][:12]}"
    for system, data in metrics.items():
        notes = summary_notes(manifest, system) + (["Published with --allow-partial."] if problems else [])
        summary = build_summary(
            run_id=run_id, system=system, metrics=data, generated_at=datetime.fromisoformat(manifest["generated_at"]),
            git_sha=sha, dataset_version=dataset,
            failure_table=table, notes=notes,
        )  # fmt: skip
        path = summaries_dir / f"{run_id}-{system}.json"
        path.write_text(summary.model_dump_json(indent=2) + "\n", encoding="utf-8")
        typer.echo(f"wrote {path}")
    typer.echo(f"wrote {docs_dir / 'results.md'}, {docs_dir / 'failures.md'}, and {target}")


def estimate(
    run_dir: Annotated[Path, typer.Argument(help="A measured run (a dev run with the model).")],
    scenarios: Annotated[int, typer.Option("--scenarios", help="Scenarios in the projected run.")] = 332,
    simulated: Annotated[int, typer.Option("--simulated", help="Simulated scenarios in the projected run.")] = 68,
    judge_sample: Annotated[int, typer.Option("--judge-sample")] = 100,
    price_model: Annotated[str, typer.Option("--price-model", help="Model id to price the tokens at.")] = "",
    budget_usd: Annotated[float, typer.Option("--budget-usd", envvar="EVAL_BUDGET_USD")] = 25.0,
) -> None:
    """Project calls, wall clock, and cost of a run from a measured run's calls per case and latency per call."""
    _, _, results = load_run(run_dir)
    prices = PriceTable.from_yaml(LLMSettings().prices_file)
    projection = estimate_run(results, scenarios=scenarios, simulated=simulated, judge_sample=judge_sample,
                              prices=prices, price_model=price_model or None)  # fmt: skip
    (run_dir / "estimate.json").write_text(json.dumps(projection, indent=2, default=str) + "\n", encoding="utf-8")
    for key, value in projection.items():
        typer.echo(f"{key}: {value}")
    cost = projection.get("projected_cost_usd")
    if cost is not None and Decimal(str(cost)) > Decimal(str(budget_usd)):
        typer.echo(f"projected cost {cost} USD is above the budget cap {budget_usd} USD: ask the human first", err=True)
        raise typer.Exit(3)
