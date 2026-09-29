"""``bank-eval run``, ``report``, and ``compare``."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Annotated, Any, Literal, cast

import typer

from bank_agent.domain.errors import ConfigurationError
from bank_evals.graders.model import CaseResult
from bank_evals.reports.markdown import render_report
from bank_evals.retrieval.tracking import MlflowTracker
from bank_evals.runner.cases import RESULTS, read_results
from bank_evals.runner.llm import LlmMode
from bank_evals.runner.run import DEFAULT_OUT, RunOptions, execute
from bank_evals.scenarios.model import Split
from bank_evals.scenarios.store import LockMismatchError

SYSTEMS_HELP = "Comma-separated systems: b0, p, b1."
_SETTING = re.compile(r"^([A-Za-z_]+)=(.*)$")


def parse_overrides(values: list[str]) -> dict[str, Any]:
    """``WORKFLOW_ROUTER=tfidf@champion`` or ``router=tfidf@champion`` into WorkflowSettings fields."""
    out: dict[str, Any] = {}
    for item in values:
        match = _SETTING.match(item)
        if match is None:
            raise typer.BadParameter(f"--set takes KEY=VALUE, got {item!r}")
        key = match[1].lower().removeprefix("workflow_")
        out[key] = match[2].lower() in {"true", "1"} if match[2].lower() in {"true", "false", "1", "0"} else match[2]
    return out


def load_run(directory: Path) -> tuple[dict[str, Any], dict[str, Any], list[CaseResult]]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    metrics = json.loads((directory / "metrics.json").read_text(encoding="utf-8"))
    return manifest, metrics, read_results(directory / RESULTS)


def write_report(directory: Path) -> Path:
    manifest, metrics, results = load_run(directory)
    path = directory / "report.md"
    path.write_text(render_report(manifest, metrics, results), encoding="utf-8")
    return path


def log_mlflow(directory: Path, tracking_uri: str) -> str | None:
    manifest, metrics, _ = load_run(directory)
    flat: dict[str, float] = {}
    for system, data in metrics.items():
        for scope, block in [("aggregate", data["aggregate"]), *data["workflows"].items()]:
            for name in ("safe_automated_resolution", "containment", "unsafe_outcomes", "escalation_missed"):
                value = block[name]
                if value["denominator"]:
                    flat[f"{system}.{scope}.{name}"] = value["count"] / value["denominator"]
    params = {key: str(manifest[key])[:250] for key in ("split", "llm_mode", "model_label", "scenario_set_hash",
                                                         "git_sha", "runs", "world")}  # fmt: skip
    tags = {"cassette_mode": manifest["llm_mode"], "environment": "evaluation",
            "policy_and_prompts": ",".join(manifest["prompts"])[:250]}  # fmt: skip
    report = (directory / "report.md").read_text(encoding="utf-8")
    return MlflowTracker(tracking_uri, experiment="scenarios").log_run(
        manifest["run_id"], params, flat, tags, {"report.md": report}
    )


def run(
    run_id: Annotated[str, typer.Option("--run-id", help="Output directory name under reports/eval/.")],
    split: Annotated[Split, typer.Option("--split")] = Split.DEV,
    systems: Annotated[str, typer.Option("--system", "--systems", help=SYSTEMS_HELP)] = "b0,p,b1",
    runs: Annotated[int, typer.Option("--runs", min=1, max=5)] = 1,
    repeat: Annotated[
        str, typer.Option("--repeat", help="Runs 2 and later: subset (stratified 48) or all.")
    ] = "subset",
    llm: Annotated[
        str, typer.Option("--llm", help="off, replay (cassettes), record (live, writes cassettes), or fake (smoke).")
    ] = "off",
    driver: Annotated[
        str, typer.Option("--driver", help="auto (simulated scenarios use the model) or scripted.")
    ] = "auto",
    workflow: Annotated[list[str] | None, typer.Option("--workflow", help="Only these workflows (repeatable).")] = None,
    scenario: Annotated[
        list[str] | None, typer.Option("--scenario", help="Only these scenario ids (repeatable).")
    ] = None,
    limit: Annotated[int | None, typer.Option("--limit")] = None,
    setting: Annotated[
        list[str] | None, typer.Option("--set", help="A workflow setting, e.g. WORKFLOW_ROUTER=tfidf@1")
    ] = None,
    out_dir: Annotated[Path, typer.Option("--out-dir")] = DEFAULT_OUT,
    cassette_dir: Annotated[Path | None, typer.Option("--cassette-dir")] = None,
    resume: Annotated[bool, typer.Option("--resume", help="Skip cases already in results.jsonl.")] = False,
    mlflow: Annotated[bool, typer.Option("--mlflow/--no-mlflow")] = False,
    smoke: Annotated[bool, typer.Option("--smoke", help="Only the 12-scenario smoke suite.")] = False,
    tracking_uri: Annotated[str, typer.Option(envvar="MLFLOW_TRACKING_URI")] = "file:./mlruns",
) -> None:
    """Play and grade scenarios with the chosen systems; write results.jsonl, metrics.json, and report.md."""
    if (
        llm not in {"off", "replay", "record", "fake"}
        or driver not in {"auto", "scripted"}
        or repeat not in {"subset", "all"}
    ):
        raise typer.BadParameter("--llm off|replay|record, --driver auto|scripted, --repeat subset|all")
    options = RunOptions(
        run_id=run_id,
        split=split,
        systems=tuple(s.strip() for s in systems.split(",") if s.strip()),
        runs=runs,
        repeat=cast(Literal["all", "subset"], repeat),
        llm=cast(LlmMode | Literal["fake"], llm),
        driver=cast(Literal["auto", "scripted"], driver),
        workflows=tuple(workflow or ()),
        scenario_ids=tuple(scenario or ()),
        limit=limit,
        out_dir=out_dir,
        cassette_dir=cassette_dir,
        resume=resume,
        workflow_overrides=parse_overrides(setting or []),
        smoke=smoke,
    )
    try:
        output = asyncio.run(execute(options))
    except (ConfigurationError, LockMismatchError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from error
    path = write_report(output.directory)
    for system, data in output.metrics.items():
        block = data["aggregate"]
        sar, unsafe = block["safe_automated_resolution"], block["unsafe_outcomes"]
        typer.echo(f"{system}: safe automated resolution {sar['count']}/{sar['denominator']}, "
                   f"unsafe {unsafe['count']}/{unsafe['denominator']}")  # fmt: skip
    if mlflow:
        log_mlflow(output.directory, tracking_uri)
    typer.echo(f"wrote {path.parent}/ ({output.results_count} cases, {output.manifest['wall_clock_seconds']} s)")


def report(run_dir: Annotated[Path, typer.Argument(help="reports/eval/<run_id>")]) -> None:
    """Regenerate report.md from results.jsonl and metrics.json, without any model."""
    typer.echo(f"wrote {write_report(run_dir)}")


def compare(run_dirs: Annotated[list[Path], typer.Argument(help="Two or more run directories.")]) -> None:
    """Safe automated resolution and unsafe outcomes per system and workflow, run next to run."""
    rows: dict[tuple[str, str], list[str]] = {}
    for directory in run_dirs:
        _, metrics, _ = load_run(directory)
        for system, data in metrics.items():
            for scope, block in [*data["workflows"].items(), ("aggregate", data["aggregate"])]:
                sar, unsafe = block["safe_automated_resolution"], block["unsafe_outcomes"]
                rows.setdefault((system, scope), []).append(
                    f"{sar['count']}/{sar['denominator']} | {unsafe['count']}/{unsafe['denominator']}"
                )
    typer.echo("| System | Scope | " + " | ".join(f"{d.name} SAR | unsafe" for d in run_dirs) + " |")
    for (system, scope), cells in sorted(rows.items()):
        typer.echo(f"| {system} | {scope} | " + " | ".join(cells) + " |")
