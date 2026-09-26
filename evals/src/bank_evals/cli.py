"""Command-line entry point `bank-eval`."""

import typer

from bank_evals import DISTRIBUTION_NAME, __version__

app = typer.Typer(
    name="bank-eval",
    help="Evaluation harness for the banking agent: scenarios, systems, graders, and reports.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def main() -> None:
    """Evaluation harness for the banking agent: scenarios, systems, graders, and reports."""


@app.command()
def version() -> None:
    """Print the distribution name and version."""
    typer.echo(f"{DISTRIBUTION_NAME} {__version__}")
