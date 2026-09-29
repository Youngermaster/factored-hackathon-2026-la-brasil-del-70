"""Thin CLI for independently resumable EDA phases."""

from pathlib import Path
from typing import Annotated

import typer

from bank_data.eda.core import PHASES, read_json

app = typer.Typer(help="Reproducible local EDA. Inputs are read-only; artifacts stay under data/eda.")


def execute(name: str, run: Path) -> None:
    from bank_data.eda.analyze import analyze
    from bank_data.eda.curate import curate
    from bank_data.eda.profile import profile
    from bank_data.eda.report import report

    functions = {"profile": profile, "curate": curate, "analyze": analyze, "report": report}
    typer.echo(f"Starting {name}: {run.name}")
    try:
        functions[name](run)
    except Exception as error:
        typer.echo(
            f"Phase failed ({type(error).__name__}). Inspect aggregate status.json; raw errors are suppressed.",
            err=True,
        )
        raise typer.Exit(1) from None
    typer.echo(f"Completed {name}: {run.name}")


@app.command("inventory")
def inventory_command(
    source: Annotated[Path, typer.Option()] = Path("data"),
    output: Annotated[Path, typer.Option()] = Path("data/eda"),
) -> None:
    from bank_data.eda.inventory import inventory

    typer.echo(str(inventory(source, output)))


@app.command("profile")
def profile_command(run_dir: Annotated[Path, typer.Argument(exists=True, file_okay=False)]) -> None:
    execute("profile", run_dir)


@app.command("curate")
def curate_command(run_dir: Annotated[Path, typer.Argument(exists=True, file_okay=False)]) -> None:
    execute("curate", run_dir)


@app.command("analyze")
def analyze_command(run_dir: Annotated[Path, typer.Argument(exists=True, file_okay=False)]) -> None:
    execute("analyze", run_dir)


@app.command("report")
def report_command(run_dir: Annotated[Path, typer.Argument(exists=True, file_okay=False)]) -> None:
    execute("report", run_dir)


@app.command("run")
def run_command(
    source: Annotated[Path, typer.Option()] = Path("data"),
    output: Annotated[Path, typer.Option()] = Path("data/eda"),
) -> None:
    from bank_data.eda.inventory import inventory

    run = inventory(source, output)
    typer.echo(f"Run directory: {run}")
    for name in PHASES[1:]:
        if read_json(run / "status.json").get(name, {}).get("state") == "complete":
            typer.echo(f"Reusing completed phase: {name}")
        else:
            execute(name, run)
