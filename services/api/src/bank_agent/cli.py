"""Command-line entry point `bank-agent`."""

import asyncio

import typer

from bank_agent import DISTRIBUTION_NAME, __version__
from bank_agent.adapters.persistence.postgres import migrate
from bank_agent.adapters.persistence.postgres.database import create_engine
from bank_agent.bootstrap.persistence import owner_database_url
from bank_agent.bootstrap.settings import load_settings

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


db_app = typer.Typer(help="Database schema commands (run as the owner role).", no_args_is_help=True)
app.add_typer(db_app, name="db")


@db_app.command("upgrade")
def db_upgrade() -> None:
    """Apply every pending migration as the owner role (POSTGRES_ADMIN_USER and POSTGRES_ADMIN_PASSWORD)."""
    settings = load_settings()
    if not settings.database.admin_password:
        typer.echo("POSTGRES_ADMIN_PASSWORD is not set", err=True)
        raise typer.Exit(2)

    async def _run() -> str | None:
        engine = create_engine(owner_database_url(settings.database), pooled=False)
        try:
            await migrate.upgrade(engine, app_role=settings.database.app_user)
            return await migrate.current_revision(engine)
        finally:
            await engine.dispose()

    typer.echo(f"schema at revision {asyncio.run(_run())}")
