"""``bank-eval scenarios``: generate, check, and lock the scenario set."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from bank_evals.scenarios.generate import DEFAULT_SEED, generate
from bank_evals.scenarios.leakage import against_router_seeds, cross_split, router_seed_texts
from bank_evals.scenarios.lint import lint
from bank_evals.scenarios.model import Split
from bank_evals.scenarios.store import (
    DATA_DIR,
    LOCK_FILE,
    LockMismatchError,
    check_lock,
    dumps,
    load_split,
    split_path,
    write_lock,
    write_split,
)
from bank_evals.world import build_world

app = typer.Typer(name="scenarios", help="Generate, check, and lock the evaluation scenarios.", no_args_is_help=True)


def problems_of(scenarios: dict[Split, list]) -> list[str]:  # type: ignore[type-arg]
    found = [f"{split.value}: {problem}" for split, items in scenarios.items() for problem in lint(items, split)]
    found += cross_split(scenarios[Split.DEV], scenarios[Split.TEST])
    found += against_router_seeds([*scenarios[Split.DEV], *scenarios[Split.TEST]], router_seed_texts())
    return found


@app.command("generate")
def generate_command(
    seed: Annotated[str, typer.Option("--seed")] = DEFAULT_SEED,
    out_dir: Annotated[Path, typer.Option("--out-dir")] = DATA_DIR,
    relock: Annotated[bool, typer.Option("--relock", help="Accept a changed test split and move its lock.")] = False,
) -> None:
    """Generate both splits deterministically, lint them, check leakage, and write them."""
    scenarios = generate(build_world(), seed)
    problems = problems_of(scenarios)
    if problems:
        for problem in problems:
            typer.echo(problem, err=True)
        raise typer.Exit(1)
    test_file, lock = split_path(Split.TEST, out_dir), out_dir / LOCK_FILE.name
    if lock.exists() and test_file.exists() and not relock:
        current = test_file.read_text(encoding="utf-8")
        if current != dumps(scenarios[Split.TEST]):
            typer.echo("the frozen test split would change; rerun with --relock to accept it", err=True)
            raise typer.Exit(1)
    for split, items in scenarios.items():
        write_split(items, split_path(split, out_dir))
    digest = write_lock(test_file, lock)
    typer.echo(f"dev {len(scenarios[Split.DEV])}, test {len(scenarios[Split.TEST])}; test lock {digest[:16]}")


@app.command("check")
def check_command(directory: Annotated[Path, typer.Option("--dir")] = DATA_DIR) -> None:
    """Lint the committed splits, check leakage, and check the test set lock."""
    scenarios = {split: load_split(split_path(split, directory)) for split in (Split.DEV, Split.TEST)}
    problems = problems_of(scenarios)
    try:
        check_lock(split_path(Split.TEST, directory), directory / LOCK_FILE.name)
    except LockMismatchError as error:
        problems.append(str(error))
    for problem in problems:
        typer.echo(problem, err=True)
    if problems:
        raise typer.Exit(1)
    typer.echo(f"dev {len(scenarios[Split.DEV])}, test {len(scenarios[Split.TEST])}: lint, leakage, and lock pass")
