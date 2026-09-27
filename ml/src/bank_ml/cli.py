"""Command-line entry point `bank-ml`."""

import typer

from bank_ml import DISTRIBUTION_NAME, __version__
from bank_ml.resolver.command import app as resolver_app
from bank_ml.risk.command import app as risk_app
from bank_ml.router.command import app as router_app

app = typer.Typer(
    name="bank-ml",
    help="Learned components for the banking agent: intent router, transaction resolver, and risk estimator.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(router_app, name="router")
app.add_typer(resolver_app, name="resolver")
app.add_typer(risk_app, name="risk")


@app.callback()
def main() -> None:
    """Learned components for the banking agent: intent router, transaction resolver, and risk estimator."""


@app.command()
def version() -> None:
    """Print the distribution name and version."""
    typer.echo(f"{DISTRIBUTION_NAME} {__version__}")
