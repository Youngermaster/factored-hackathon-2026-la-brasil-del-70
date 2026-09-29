"""``bank-eval judge``: rate a stratified sample of a run's transcripts, export them for human raters, and report
the agreement once human ratings exist."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated, Any, cast

import typer

from bank_evals.commands.run import load_run
from bank_evals.judge import agreement, judge, stratified_sample, transcript_text
from bank_evals.meta import REPOSITORY_ROOT
from bank_evals.runner.llm import LlmMode, build_run_llm
from bank_evals.runner.wiring import HarnessSettings, prompt_registry

SAMPLE_FILE = "judge_sample.jsonl"


def sample_rows(run_dir: Path, size: int, llm_mode: str) -> list[dict[str, Any]]:
    manifest, _, results = load_run(run_dir)
    sample = stratified_sample(results, size)
    cassettes = REPOSITORY_ROOT / "evals" / "cassettes" / "runs" / f"{manifest['run_id']}-judge"
    llm = build_run_llm(HarnessSettings().llm, prompt_registry(), cast(LlmMode, llm_mode), cassette_dir=cassettes)

    async def rate_all() -> list[dict[str, Any]]:
        rows = []
        for result in sample:
            view = await judge(llm.client, result) if llm.available else None
            rows.append({
                "run_id": result.run_id, "system": result.system, "scenario_id": result.scenario_id,
                "workflow": result.workflow, "language": result.language, "dialect": result.dialect,
                "transcript": transcript_text(result), "judge": view.model_dump() if view else None, "human": None,
            })  # fmt: skip
        return rows

    return asyncio.run(rate_all())


def judge_command(
    run_dir: Annotated[Path, typer.Argument(help="reports/eval/<run_id>")],
    size: Annotated[int, typer.Option("--sample")] = 100,
    llm: Annotated[str, typer.Option("--llm", help="off, replay, or record")] = "off",
    ratings: Annotated[Path | None, typer.Option("--ratings", help="A sample file with human ratings filled")] = None,
) -> None:
    """Judge a stratified sample (or, with --ratings, compute judge and human agreement)."""
    if ratings is not None:
        rows = [json.loads(line) for line in ratings.read_text(encoding="utf-8").splitlines() if line.strip()]
        result = agreement(rows)
    else:
        rows = sample_rows(run_dir, size, llm)
        with (run_dir / SAMPLE_FILE).open("w", encoding="utf-8") as handle:
            handle.writelines(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
        result = agreement(rows)
        typer.echo(
            f"wrote {run_dir / SAMPLE_FILE} ({len(rows)} transcripts, {sum(1 for r in rows if r['judge'])} judged)"
        )
    (run_dir / "judge_agreement.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    typer.echo(json.dumps(result))
