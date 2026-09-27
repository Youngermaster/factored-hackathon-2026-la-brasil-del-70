"""Command-line entry point `bank-data`."""

import typer

from bank_data import DISTRIBUTION_NAME, __version__
from bank_data.eda.cli import app as eda_app

app = typer.Typer(
    name="bank-data",
    help="Data platform for the banking agent: ingestion, contracts, transformations, and reports.",
    no_args_is_help=True,
    add_completion=False,
)

app.add_typer(eda_app, name="eda")


@app.callback()
def main() -> None:
    """Data platform for the banking agent: ingestion, contracts, transformations, and reports."""


@app.command()
def version() -> None:
    """Print the distribution name and version."""
    typer.echo(f"{DISTRIBUTION_NAME} {__version__}")
