"""Command-line entry point `bank-agent`."""

import typer

from bank_agent import DISTRIBUTION_NAME, __version__

app = typer.Typer(
    name="bank-agent",
    help="Banking customer-service API and its operational commands.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def main() -> None:
    """Banking customer-service API and its operational commands."""


@app.command()
def version() -> None:
    """Print the distribution name and version."""
    typer.echo(f"{DISTRIBUTION_NAME} {__version__}")
