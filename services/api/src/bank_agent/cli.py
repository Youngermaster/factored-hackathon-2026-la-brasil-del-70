"""Command-line entry point `bank-agent`."""

import asyncio
import json
import time
from pathlib import Path

import typer

from bank_agent import DISTRIBUTION_NAME, __version__
from bank_agent.adapters.persistence.postgres import migrate
from bank_agent.adapters.persistence.postgres.database import create_engine
from bank_agent.adapters.persistence.postgres.retention import PostgresRetentionPurge
from bank_agent.adapters.policy.tasks import write_catalog, write_lock
from bank_agent.adapters.retrieval.embedding import DEFAULT_EMBEDDING_MODEL
from bank_agent.adapters.system.clock import SystemClock
from bank_agent.bootstrap.persistence import owner_database_url
from bank_agent.bootstrap.settings import (
    DEFAULT_EMBEDDING_CACHE_DIR,
    DEFAULT_INDEX_DIR,
    DEFAULT_MODEL_CACHE_DIR,
    DEFAULT_POLICY_DIR,
    AppSettings,
    load_settings,
)
from bank_agent.domain.errors import ConfigurationError, PolicyPackInvalidError
from bank_agent.domain.retention import PurgeReport, RetentionPolicy

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


retention_app = typer.Typer(help="Retention commands (run as the owner role).", no_args_is_help=True)
app.add_typer(retention_app, name="retention")
SECONDS_PER_HOUR = 3600


def _purge_once(settings: AppSettings, policy: RetentionPolicy, *, dry_run: bool) -> PurgeReport:
    async def _run() -> PurgeReport:
        engine = create_engine(owner_database_url(settings.database), pooled=False)
        try:
            return await PostgresRetentionPurge(engine).purge(policy, SystemClock().now(), dry_run=dry_run)
        finally:
            await engine.dispose()

    return asyncio.run(_run())


@retention_app.command("purge")
def retention_purge(
    dry_run: bool = typer.Option(False, help="Count what would be deleted, then roll back."),
    every_hours: float = typer.Option(0.0, min=0.0, help="Repeat every N hours (0 runs once); failures are retried."),
) -> None:
    """Delete conversation text, ended sessions, challenges, trust events, closed intakes, and old rate windows."""
    settings = load_settings(owner=True)
    if not settings.database.admin_password:
        typer.echo("POSTGRES_ADMIN_PASSWORD is not set", err=True)
        raise typer.Exit(2)
    retention = settings.retention
    policy = RetentionPolicy(
        conversation_days=retention.conversation_days,
        session_days=retention.session_days,
        credit_application_days=retention.credit_application_days,
    )
    while True:
        try:
            report = _purge_once(settings, policy, dry_run=dry_run)
        except Exception as error:
            if every_hours <= 0:
                raise
            typer.echo(json.dumps({"event": "retention_purge_failed", "error": type(error).__name__}), err=True)
        else:
            summary = {"event": "retention_purge", "dry_run": report.dry_run, "total": report.total}
            typer.echo(json.dumps({**summary, "counts": report.counts()}))
        if every_hours <= 0:
            return
        time.sleep(every_hours * SECONDS_PER_HOUR)


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


@index_app.command("qdrant")
def index_qdrant(
    url: str = typer.Option("", help="Qdrant's REST base; default RETRIEVAL_QDRANT_URL."),
    recreate: bool = typer.Option(False, help="Drop the collection first (after a change of the indexing code)."),
) -> None:
    """Embed the pack's clauses with the hosted model and upsert them into Qdrant (idempotent; ADR 0047).

    Unlike `index build`, this reads the environment: POLICY_DIR, RETRIEVAL_HOSTED_EMBEDDING_MODEL and its
    dimensions, RETRIEVAL_QDRANT_URL, and the embedding key and base (LLM_API_KEY_PRIMARY, LLM_API_BASE or
    RETRIEVAL_EMBEDDING_API_BASE). In production it runs inside the api container, which has the key and egress.
    """
    from bank_agent.adapters.policy.filesystem import FilesystemPolicyRepository
    from bank_agent.adapters.retrieval.corpus import build_corpus
    from bank_agent.adapters.retrieval.vector_index import VectorClauseIndex
    from bank_agent.adapters.telemetry.noop import NoopTelemetry
    from bank_agent.adapters.vector.qdrant import QdrantVectorStore
    from bank_agent.bootstrap.embeddings import build_hosted_embedder
    from bank_agent.bootstrap.settings import SettingsError
    from bank_agent.domain.errors import RetrievalBackendError

    try:
        settings = load_settings()
        repository = FilesystemPolicyRepository.from_directory(settings.policy.dir)
        embedder = build_hosted_embedder(
            settings.retrieval, settings.llm, clock=SystemClock(), telemetry=NoopTelemetry()
        )
        store = QdrantVectorStore(url or settings.retrieval.qdrant_url, timeout_seconds=30.0)
        clauses = VectorClauseIndex(store, embedder, pack_version=repository.pack_version())
        if recreate and store.delete_collection(clauses.name):
            typer.echo(f"dropped {clauses.name}")
        report = clauses.build(build_corpus(repository))
    except (ConfigurationError, SettingsError, RetrievalBackendError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from error
    typer.echo(
        f"{'created' if report.created else 'updated'} {report.collection}: {report.points} points, "
        f"model {report.model_id}"
    )
