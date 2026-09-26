"""Resolve the explicit source into a warehouse directory, a data source adapter, and a dbt target.

One source, one warehouse: ``sample`` (the committed ``data_platform/sample/``) builds under
``data/warehouse-sample``, ``s3`` (the organizer bucket) under ``data/warehouse``, and ``local`` (any directory,
used by fixtures and tests) under ``data/warehouse-local`` unless ``BANK_DATA_WAREHOUSE_DIR`` says otherwise.
The manifest refuses a second source, so data from two origins is never mixed.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bank_data.config import SourceConfig, load_config
from bank_data.errors import ConfigurationError
from bank_data.ingest.local import LocalSource
from bank_data.ingest.s3 import S3Source
from bank_data.ingest.source import DataSource
from bank_data.settings import DBT_PROJECT_DIR, DEFAULT_SAMPLE_DIR, PipelineSettings, S3Settings, SourceKind
from bank_data.transform.dbt import DbtResources, DbtRunner, DbtTarget

DEFAULT_SAMPLE_SEED = "bank-data-sample-v1"


@dataclass(frozen=True)
class Workspace:
    source_kind: SourceKind
    warehouse_dir: Path
    config: SourceConfig
    pipeline: PipelineSettings
    local_dir: Path | None = None
    project_dir: Path = DBT_PROJECT_DIR

    @classmethod
    def resolve(
        cls,
        source: SourceKind | None = None,
        *,
        local_dir: Path | None = None,
        pipeline: PipelineSettings | None = None,
        warehouse_dir: Path | None = None,
    ) -> "Workspace":
        settings = pipeline or PipelineSettings()
        kind: SourceKind = source or settings.bank_data_source
        if kind == "local" and local_dir is None:
            raise ConfigurationError("--local-dir is required for the local source")
        if kind != "local" and local_dir is not None:
            raise ConfigurationError("--local-dir is only valid with --source local")
        return cls(
            source_kind=kind,
            warehouse_dir=warehouse_dir or settings.warehouse_dir(kind),
            config=load_config(settings.bank_data_config_file),
            pipeline=settings,
            local_dir=local_dir,
        )

    def data_source(self, s3: S3Settings | None = None) -> DataSource:
        if self.source_kind == "s3":
            return S3Source.from_settings(s3 or S3Settings())
        if self.source_kind == "sample":
            return LocalSource(DEFAULT_SAMPLE_DIR)
        if self.local_dir is None:
            raise ConfigurationError("--local-dir is required for the local source")
        return LocalSource(self.local_dir)

    @property
    def bronze_dir(self) -> Path:
        return self.warehouse_dir / "bronze"

    @property
    def manifest_path(self) -> Path:
        return self.warehouse_dir / "manifest.duckdb"

    def dbt_target(self, *, subset: bool = False) -> DbtTarget:
        name = "subset" if subset else "full"
        return DbtTarget(
            warehouse_db=self.warehouse_dir / ("warehouse-subset.duckdb" if subset else "warehouse.duckdb"),
            bronze_dir=self.bronze_dir,
            gold_dir=self.warehouse_dir / ("gold-subset" if subset else "gold"),
            work_dir=self.warehouse_dir / "dbt" / name,
        )

    def dbt(self, *, subset: bool = False) -> DbtRunner:
        resources = DbtResources(
            dbt_threads=min(self.pipeline.bank_data_duckdb_threads, 8),
            duckdb_threads=self.pipeline.bank_data_duckdb_threads,
            memory_limit=self.pipeline.bank_data_duckdb_memory_limit,
        )
        return DbtRunner(self.project_dir, self.dbt_target(subset=subset), resources)

    def dbt_variables(self, *, sample_customers: int = 0, sample_seed: str = DEFAULT_SAMPLE_SEED) -> dict[str, Any]:
        return {
            "snapshot_date": self.config.dataset.snapshot_date.isoformat(),
            "lookback_days": self.config.build.lookback_days,
            "sample_customers": sample_customers,
            "sample_seed": sample_seed,
        }
