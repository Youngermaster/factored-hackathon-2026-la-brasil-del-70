"""Command-line entry point `bank-agent`."""

import asyncio
from pathlib import Path

import typer

from bank_agent import DISTRIBUTION_NAME, __version__
from bank_agent.adapters.persistence.postgres import migrate
from bank_agent.adapters.persistence.postgres.database import create_engine
from bank_agent.adapters.policy.tasks import write_catalog, write_lock
from bank_agent.adapters.retrieval.embedding import DEFAULT_EMBEDDING_MODEL
from bank_agent.bootstrap.persistence import owner_database_url
from bank_agent.bootstrap.settings import (
    DEFAULT_EMBEDDING_CACHE_DIR,
    DEFAULT_INDEX_DIR,
    DEFAULT_MODEL_CACHE_DIR,
    DEFAULT_POLICY_DIR,
    load_settings,
)
from bank_agent.domain.errors import ConfigurationError, PolicyPackInvalidError

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
    settings = load_settings(owner=True)
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


policy_app = typer.Typer(help="Synthetic policy pack commands (they never read the environment).", no_args_is_help=True)
app.add_typer(policy_app, name="policy")
DEFAULT_CATALOG_PAGE = DEFAULT_POLICY_DIR.parent / "docs" / "policy" / "catalog.md"


@policy_app.command("lock")
def policy_lock(policy_dir: Path = DEFAULT_POLICY_DIR) -> None:
    """Rewrite the version lock after a clause change; refuses a changed clause that kept its version."""
    try:
        target = write_lock(policy_dir)
    except (ValueError, PolicyPackInvalidError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from error
    typer.echo(f"wrote {target.name}")


@policy_app.command("catalog")
def policy_catalog(policy_dir: Path = DEFAULT_POLICY_DIR, output: Path = DEFAULT_CATALOG_PAGE) -> None:
    """Regenerate the policy catalog page (clauses, rules, bindings, matrix, credit catalog)."""
    try:
        target = write_catalog(policy_dir, output)
    except PolicyPackInvalidError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from error
    typer.echo(f"wrote {target.name}")


index_app = typer.Typer(help="Retrieval index commands (they never read the environment).", no_args_is_help=True)
app.add_typer(index_app, name="index")


@index_app.command("build")
def index_build(
    policy_dir: Path = DEFAULT_POLICY_DIR,
    output: Path = DEFAULT_INDEX_DIR,
    dense: bool = typer.Option(False, help="Also embed every clause (needs the optional ml extra)."),
    model: str = DEFAULT_EMBEDDING_MODEL,
    model_cache: Path = DEFAULT_MODEL_CACHE_DIR,
    embedding_cache: Path = DEFAULT_EMBEDDING_CACHE_DIR,
) -> None:
    """Build the open-retrieval index for the pack's current version under OUTPUT/<pack version>/."""
    from bank_agent.adapters.policy.filesystem import FilesystemPolicyRepository
    from bank_agent.adapters.retrieval.index_store import build_index, write_index
    from bank_agent.bootstrap.retrieval import build_embedder

    try:
        repository = FilesystemPolicyRepository.from_directory(policy_dir)
        embedder = (
            build_embedder(model, model_cache_dir=model_cache, embedding_cache_dir=embedding_cache) if dense else None
        )
        index = build_index(repository, embedder=embedder)
    except ConfigurationError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from error
    directory = write_index(index, output)
    manifest = index.manifest
    typer.echo(
        f"wrote {directory} ({manifest.document_count} documents, tokenizer {manifest.tokenizer}, "
        f"dense {manifest.embedding_model or 'no'})"
    )
