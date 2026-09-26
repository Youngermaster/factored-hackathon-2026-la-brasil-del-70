"""Bronze and quarantine Parquet: raw rows as delivered, plus lineage columns.

Layout (``<warehouse>/bronze`` and ``<warehouse>/quarantine``)::

    bronze/<table>/process_date=YYYY-MM-DD/<object id>.parquet
    quarantine/<table>/process_date=YYYY-MM-DD/<object id>.parquet

Every data column is a string exactly as delivered (empty strings are kept; silver normalizes them). The
lineage columns are ``_source_key``, ``_etag``, ``_loaded_at``, ``_schema_hash``, ``_ingest_run_id``, plus
``_process_date`` (the partition) and ``_source_row`` (the row's position in the object, the final
deduplication tie-break). Quarantine files add ``_reason_code`` and ``_column``. One object maps to one
file in each tree, so a changed object replaces its files and nothing is appended twice.
"""

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import duckdb
import pandas as pd

from bank_data.contracts.tables import TableSpec
from bank_data.ingest.layout import FileFormat

LINEAGE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("_source_key", "varchar"),
    ("_etag", "varchar"),
    ("_loaded_at", "timestamp"),
    ("_schema_hash", "varchar"),
    ("_ingest_run_id", "varchar"),
    ("_process_date", "date"),
    ("_source_row", "bigint"),
)
QUARANTINE_COLUMNS: tuple[tuple[str, str], ...] = (("_reason_code", "varchar"), ("_column", "varchar"))
EMPTY_FILE_NAME = "_empty.parquet"
_NEVER_NULL = "\x01\x02__bank_data_no_null__"


class UnreadableObjectError(Exception):
    """The object is not a parseable CSV or Parquet file."""


def object_id(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def read_raw(path: Path, file_format: FileFormat) -> pd.DataFrame:
    """Read an object into a frame of strings; empty fields stay empty strings (never null)."""
    connection = duckdb.connect()
    try:
        if file_format == "csv":
            relation = connection.read_csv(
                str(path),
                header=True,
                all_varchar=True,
                null_padding=False,
                hive_partitioning=False,
                encoding="utf-8",
                na_values=[_NEVER_NULL],
                allow_quoted_nulls=False,
                auto_detect=True,
                sample_size=-1,
            )
        else:
            relation = connection.read_parquet(str(path), hive_partitioning=False)
            relation = relation.select(", ".join(f'cast("{name}" as varchar) as "{name}"' for name in relation.columns))
        frame = relation.df()
    except duckdb.Error as error:
        raise UnreadableObjectError(type(error).__name__) from None
    finally:
        connection.close()
    frame.columns = [str(name).strip().lstrip("\ufeff").lower() for name in frame.columns]
    return frame.astype("str")


@dataclass(frozen=True)
class Lineage:
    source_key: str
    etag: str
    loaded_at: datetime
    schema_hash: str
    run_id: str
    process_date: date


def with_lineage(frame: pd.DataFrame, lineage: Lineage) -> pd.DataFrame:
    enriched = frame.copy()
    enriched["_source_key"] = lineage.source_key
    enriched["_etag"] = lineage.etag
    enriched["_loaded_at"] = pd.Timestamp(lineage.loaded_at)
    enriched["_schema_hash"] = lineage.schema_hash
    enriched["_ingest_run_id"] = lineage.run_id
    enriched["_process_date"] = pd.Timestamp(lineage.process_date)
    enriched["_source_row"] = pd.Series(range(1, len(frame) + 1), index=frame.index, dtype="int64")
    return enriched


def _select_list(frame: pd.DataFrame) -> str:
    casts = []
    types = dict(LINEAGE_COLUMNS + QUARANTINE_COLUMNS)
    for name in frame.columns:
        sql_type = types.get(str(name), "varchar")
        casts.append(f'cast("{name}" as {sql_type}) as "{name}"')
    return ", ".join(casts)


def write_parquet(frame: pd.DataFrame, destination: Path) -> None:
    """Write ``frame`` (strings plus lineage columns) atomically with zstd compression."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".partial")
    connection = duckdb.connect()
    try:
        connection.register("frame", frame)
        connection.execute(
            f"copy (select {_select_list(frame)} from frame) to '{partial.as_posix()}' "  # noqa: S608 (local paths and known column names)
            "(format parquet, compression zstd)"
        )
    finally:
        connection.close()
    partial.replace(destination)


class BronzeStore:
    """Paths and file operations for bronze and quarantine."""

    def __init__(self, warehouse_dir: Path) -> None:
        self.bronze_dir = warehouse_dir / "bronze"
        self.quarantine_dir = warehouse_dir / "quarantine"

    def _path(self, root: Path, table: str, process_date: date, key: str) -> Path:
        return root / table / f"process_date={process_date.isoformat()}" / f"{object_id(key)}.parquet"

    def bronze_path(self, table: str, process_date: date, key: str) -> Path:
        return self._path(self.bronze_dir, table, process_date, key)

    def quarantine_path(self, table: str, process_date: date, key: str) -> Path:
        return self._path(self.quarantine_dir, table, process_date, key)

    def remove_object(self, table: str, process_date: date, key: str) -> None:
        """Delete the bronze and quarantine files of ``key`` before it is reloaded.

        An object's partition follows from its key (and, for snapshots, the configured snapshot date), so the
        paths are computed rather than searched; changing the snapshot date needs a fresh warehouse.
        """
        self.bronze_path(table, process_date, key).unlink(missing_ok=True)
        self.quarantine_path(table, process_date, key).unlink(missing_ok=True)

    def existing_keys(
        self, table: str, process_date: date, key: str, primary_key: tuple[str, ...]
    ) -> set[tuple[str, ...]]:
        """Primary keys currently in bronze for ``key`` (to detect rows a re-delivery removed)."""
        path = self.bronze_path(table, process_date, key)
        if not path.exists():
            return set()
        columns = ", ".join(f'"{column}"' for column in primary_key)
        connection = duckdb.connect()
        try:
            rows = connection.execute(
                f"select distinct {columns} from read_parquet(?)",  # noqa: S608 (known column names)
                [path.as_posix()],
            ).fetchall()
        finally:
            connection.close()
        return {tuple(str(value) for value in row) for row in rows}

    def ensure_placeholder(self, spec: TableSpec) -> None:
        """Keep a zero-row file per table so every bronze glob matches, even before the first object."""
        path = self.bronze_dir / spec.name / EMPTY_FILE_NAME
        if path.exists():
            return
        columns = {name: pd.Series([], dtype="str") for name in spec.column_names}
        frame = pd.DataFrame(columns)
        for name, sql_type in LINEAGE_COLUMNS:
            if sql_type == "timestamp" or sql_type == "date":
                frame[name] = pd.Series([], dtype="datetime64[ns]")
            elif sql_type == "bigint":
                frame[name] = pd.Series([], dtype="int64")
            else:
                frame[name] = pd.Series([], dtype="str")
        write_parquet(frame, path)
