"""Pipeline steps shared by the CLI and the integration tests: ingest, build, and test."""

import logging

from bank_data.errors import ConfigurationError
from bank_data.ingest.manifest import Manifest
from bank_data.ingest.runner import IngestReport, IngestRunner
from bank_data.settings import S3Settings
from bank_data.transform.codegen import stale_files
from bank_data.workspace import DEFAULT_SAMPLE_SEED, Workspace

LOGGER = logging.getLogger("bank_data.pipeline")


def ingest(workspace: Workspace, *, download_only: bool = False, s3: S3Settings | None = None) -> IngestReport:
    runner = IngestRunner(
        workspace.data_source(s3),
        workspace.warehouse_dir,
        snapshot_date=workspace.config.dataset.snapshot_date,
        workers=workspace.pipeline.bank_data_ingest_workers,
        type_change_threshold=workspace.config.ingest.type_change_threshold,
    )
    return runner.run(download_only=download_only)


def ensure_codegen_current(workspace: Workspace) -> None:
    stale = stale_files(workspace.project_dir, workspace.config)
    if stale:
        names = ", ".join(path.name for path in stale)
        raise ConfigurationError(f"generated dbt files are out of date ({names}); run `bank-data codegen`")


def build(
    workspace: Workspace,
    *,
    sample_customers: int = 0,
    sample_seed: str = DEFAULT_SAMPLE_SEED,
    full_refresh: bool = False,
) -> str:
    """Build silver and gold (with their tests). Honors full refreshes requested by re-deliveries."""
    ensure_codegen_current(workspace)
    if not workspace.manifest_path.exists():
        raise ConfigurationError("no manifest in this warehouse; run `bank-data ingest` first")
    subset = sample_customers > 0
    with Manifest(workspace.manifest_path) as manifest:
        pending = manifest.pending_full_refresh()
    if pending:
        LOGGER.warning("full refresh requested by re-delivered objects", extra={"tables": ",".join(pending)})
    runner = workspace.dbt(subset=subset)
    variables = workspace.dbt_variables(sample_customers=sample_customers, sample_seed=sample_seed)
    output = runner.build(variables, full_refresh=full_refresh or bool(pending))
    if pending and not subset:
        with Manifest(workspace.manifest_path) as manifest:
            manifest.clear_full_refresh()
    return output


def run_tests(workspace: Workspace, *, sample_customers: int = 0, sample_seed: str = DEFAULT_SAMPLE_SEED) -> str:
    """dbt tests plus source freshness against the thresholds in the source configuration."""
    runner = workspace.dbt(subset=sample_customers > 0)
    variables = workspace.dbt_variables(sample_customers=sample_customers, sample_seed=sample_seed)
    return runner.test(variables) + runner.freshness(variables)
