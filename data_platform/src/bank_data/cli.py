"""Command-line entry point `bank-data`."""

import typer

from bank_data import DISTRIBUTION_NAME, __version__

app = typer.Typer(
    name="bank-data",
    help="Data platform for the banking agent: ingestion, contracts, transformations, and reports.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def main() -> None:
    """Data platform for the banking agent: ingestion, contracts, transformations, and reports."""


@app.command()
def version() -> None:
    """Print the distribution name and version."""
    typer.echo(f"{DISTRIBUTION_NAME} {__version__}")
