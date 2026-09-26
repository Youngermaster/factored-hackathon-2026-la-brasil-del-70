"""Command-line entry point `bank-ml`."""

import typer

from bank_ml import DISTRIBUTION_NAME, __version__

app = typer.Typer(
    name="bank-ml",
    help="Learned components for the banking agent: intent router and transaction resolver.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def main() -> None:
    """Learned components for the banking agent: intent router and transaction resolver."""


@app.command()
def version() -> None:
    """Print the distribution name and version."""
    typer.echo(f"{DISTRIBUTION_NAME} {__version__}")
