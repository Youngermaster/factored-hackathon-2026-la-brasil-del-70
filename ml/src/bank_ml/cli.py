"""Command-line entry point `bank-ml`."""

import typer

from bank_ml import DISTRIBUTION_NAME, __version__
from bank_ml.router.command import app as router_app

app = typer.Typer(
    name="bank-ml",
    help="Learned components for the banking agent: intent router and transaction resolver.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(router_app, name="router")


@app.callback()
def main() -> None:
    """Learned components for the banking agent: intent router and transaction resolver."""


@app.command()
def version() -> None:
    """Print the distribution name and version."""
    typer.echo(f"{DISTRIBUTION_NAME} {__version__}")
