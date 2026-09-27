"""Shared helpers for the data platform integration tests: fixture copies, pipeline runs, table hashes."""

import shutil
from pathlib import Path

import duckdb

from bank_data import pipeline
from bank_data.ingest.runner import IngestReport
from bank_data.settings import DATA_PLATFORM_ROOT, PipelineSettings
from bank_data.workspace import Workspace

FIXTURE_ROOT = DATA_PLATFORM_ROOT / "fixtures" / "late_arrival"
VOLATILE_COLUMNS = frozenset({"_loaded_at", "_ingest_run_id"})
"""Lineage columns that legitimately differ between runs; everything else must match."""


def copy_parts(destination: Path, *parts: str) -> Path:
    """Merge fixture parts (``base``, ``late``, ``breaking``) into ``destination``."""
    destination.mkdir(parents=True, exist_ok=True)
    for part in parts:
        shutil.copytree(FIXTURE_ROOT / part, destination, dirs_exist_ok=True)
    return destination


def workspace(source_dir: Path, warehouse: Path) -> Workspace:
    settings = PipelineSettings(
        bank_data_duckdb_threads=2, bank_data_ingest_workers=2, bank_data_duckdb_memory_limit="1GB"
    )
    return Workspace.resolve("local", local_dir=source_dir, pipeline=settings, warehouse_dir=warehouse)


def ingest_and_build(space: Workspace, *, full_refresh: bool = False) -> IngestReport:
    report = pipeline.ingest(space)
    pipeline.build(space, full_refresh=full_refresh)
    return report


def table_hashes(warehouse_db: Path) -> dict[str, tuple[int, str]]:
    """Row count and an order-independent content hash of every silver and gold relation."""
    connection = duckdb.connect(str(warehouse_db), read_only=True)
    try:
        relations = connection.execute(
            "select table_schema, table_name from information_schema.tables "
            "where table_schema in ('silver', 'gold') order by 1, 2"
        ).fetchall()
        hashes: dict[str, tuple[int, str]] = {}
        for schema, name in relations:
            columns = [
                str(row[0])
                for row in connection.execute(
                    "select column_name from information_schema.columns where table_schema = ? and table_name = ? "
                    "order by ordinal_position",
                    [schema, name],
                ).fetchall()
                if str(row[0]) not in VOLATILE_COLUMNS
            ]
            projection = ", ".join(f'"{column}"' for column in columns)
            count, digest = connection.execute(
                f"select count(*), coalesce(md5(string_agg(row_text, chr(10) order by row_text)), '') "  # noqa: S608
                f"from (select cast(struct_pack({projection}) as varchar) as row_text from {schema}.{name})"
            ).fetchone() or (0, "")
            hashes[f"{schema}.{name}"] = (int(count), str(digest))
        return hashes
    finally:
        connection.close()
