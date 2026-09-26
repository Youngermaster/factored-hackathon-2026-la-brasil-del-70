"""Command-line entry point ``bank-data``.

Every command takes the explicit source (``--source sample|s3|local``; default ``BANK_DATA_SOURCE``, which
defaults to ``sample``). Exit codes: 0 success, 1 a failed object or step, 2 configuration, 3 a breaking
schema change (batch quarantined), 4 source access, 5 dbt, 6 sample bounds. Output never contains
credentials or the bucket name.
"""

from pathlib import Path
from typing import Annotated

import typer

from bank_data import DISTRIBUTION_NAME, __version__, pipeline
from bank_data.errors import DataPlatformError
from bank_data.logs import configure_logging
from bank_data.settings import DEFAULT_SAMPLE_DIR, REPOSITORY_ROOT, S3Settings, SourceKind
from bank_data.transform.codegen import stale_files, write_generated
from bank_data.workspace import DEFAULT_SAMPLE_SEED, Workspace

app = typer.Typer(
    name="bank-data",
    help="Data platform for the banking agent: ingestion, contracts, transformations, and reports.",
    no_args_is_help=True,
    add_completion=False,
)

SourceOption = Annotated[
    SourceKind | None,
    typer.Option("--source", help="sample (committed, offline), s3 (organizer bucket), or local (--local-dir)."),
]
LocalDirOption = Annotated[
    Path | None, typer.Option("--local-dir", help="Directory laid out like the bucket prefix (source local).")
]
SampleOption = Annotated[
    int, typer.Option("--sample-customers", min=0, help="Build from N customers chosen by a seeded hash (0: all).")
]
SeedOption = Annotated[str, typer.Option("--seed", help="Seed of the customer hash.")]


def _workspace(source: SourceKind | None, local_dir: Path | None) -> Workspace:
    s3 = S3Settings()
    configure_logging(s3.secret_values())
    return Workspace.resolve(source, local_dir=local_dir)


def _fail(error: DataPlatformError) -> typer.Exit:
    typer.echo(str(error), err=True)
    return typer.Exit(error.exit_code)


@app.callback()
def main() -> None:
    """Data platform for the banking agent: ingestion, contracts, transformations, and reports."""


@app.command()
def version() -> None:
    """Print the distribution name and version."""
    typer.echo(f"{DISTRIBUTION_NAME} {__version__}")


@app.command()
def ingest(
    source: SourceOption = None,
    local_dir: LocalDirOption = None,
    download_only: Annotated[bool, typer.Option("--download-only", help="Download to raw/ without loading.")] = False,
) -> None:
    """Download new or changed objects (manifest-driven), validate contracts, and write bronze or quarantine."""
    try:
        workspace = _workspace(source, local_dir)
        report = pipeline.ingest(workspace, download_only=download_only)
    except DataPlatformError as error:
        raise _fail(error) from None
    counts = report.counts()
    typer.echo(
        f"source={report.source_label} run={report.run_id} listed={report.listed} new={report.new} "
        f"changed={report.changed} unchanged={report.unchanged} skipped={report.skipped} "
        f"loaded={counts['loaded']} quarantined_objects={counts['quarantined']} failed={counts['failed']} "
        f"rows_loaded={counts['rows_loaded']} rows_quarantined={counts['rows_quarantined']}"
    )
    for key, code in report.outstanding_quarantined:
        typer.echo(f"quarantined batch: {key} ({code})", err=True)
    raise typer.Exit(report.exit_code)


@app.command()
def build(
    source: SourceOption = None,
    local_dir: LocalDirOption = None,
    sample_customers: SampleOption = 0,
    seed: SeedOption = DEFAULT_SAMPLE_SEED,
    full_refresh: Annotated[bool, typer.Option("--full-refresh", help="Rebuild incremental models.")] = False,
) -> None:
    """Build silver and gold with dbt (models and tests); incremental unless a full refresh is needed."""
    try:
        workspace = _workspace(source, local_dir)
        pipeline.build(workspace, sample_customers=sample_customers, sample_seed=seed, full_refresh=full_refresh)
    except DataPlatformError as error:
        raise _fail(error) from None
    typer.echo(f"built source={workspace.source_kind} warehouse={_shown(workspace.warehouse_dir)}")


@app.command("test")
def run_tests(
    source: SourceOption = None,
    local_dir: LocalDirOption = None,
    sample_customers: SampleOption = 0,
    seed: SeedOption = DEFAULT_SAMPLE_SEED,
) -> None:
    """Run the dbt tests and the source freshness checks."""
    try:
        workspace = _workspace(source, local_dir)
        pipeline.run_tests(workspace, sample_customers=sample_customers, sample_seed=seed)
    except DataPlatformError as error:
        raise _fail(error) from None
    typer.echo("tests and freshness passed")


@app.command()
def codegen(
    check: Annotated[bool, typer.Option("--check", help="Fail when a generated file is out of date.")] = False,
) -> None:
    """Write the dbt sources, silver contracts, and canonical seed from the table specs."""
    try:
        workspace = Workspace.resolve("sample")
    except DataPlatformError as error:
        raise _fail(error) from None
    if check:
        stale = stale_files(workspace.project_dir, workspace.config)
        for path in stale:
            typer.echo(f"out of date: {_shown(path)}", err=True)
        raise typer.Exit(1 if stale else 0)
    for path in write_generated(workspace.project_dir, workspace.config):
        typer.echo(f"wrote {_shown(path)}")


def _shown(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


__all__ = ["DEFAULT_SAMPLE_DIR", "app"]
