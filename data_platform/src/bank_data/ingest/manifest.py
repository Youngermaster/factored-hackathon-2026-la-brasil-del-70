"""The ingestion manifest: one DuckDB file that records every object, run, schema event, and backlog item.

``objects`` has the columns the phase requires (object key, etag, size, last modified, discovered at, loaded
at, status, schema hash, row count, error code) plus the table, partition, row split, source, and run.
Diffing listed objects against it decides what an ingest run downloads, which makes ``bank-data ingest``
incremental and idempotent: an unchanged object (same key and etag, already loaded or quarantined) is never
downloaded or loaded again.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path

import duckdb

from bank_data.errors import SourceMismatchError
from bank_data.ingest.source import SourceObject


class ObjectStatus(StrEnum):
    DISCOVERED = "discovered"
    DOWNLOADED = "downloaded"
    LOADED = "loaded"
    QUARANTINED = "quarantined"
    """The whole batch is quarantined (breaking schema change or unreadable file)."""
    FAILED = "failed"
    SKIPPED = "skipped"


SETTLED = frozenset({ObjectStatus.LOADED, ObjectStatus.QUARANTINED, ObjectStatus.SKIPPED})

_SCHEMA = """
create table if not exists objects (
    object_key varchar primary key,
    table_name varchar,
    process_date date,
    etag varchar not null,
    size bigint not null,
    last_modified timestamptz not null,
    discovered_at timestamp not null,
    loaded_at timestamp,
    status varchar not null,
    schema_hash varchar,
    row_count bigint,
    bronze_rows bigint,
    quarantined_rows bigint,
    error_code varchar,
    source_label varchar not null,
    ingest_run_id varchar,
    contract_version varchar
);
create table if not exists runs (
    run_id varchar primary key,
    source_label varchar not null,
    started_at timestamp not null,
    finished_at timestamp,
    status varchar not null,
    contract_version varchar not null,
    objects_listed bigint,
    objects_new bigint,
    objects_changed bigint,
    objects_unchanged bigint,
    objects_loaded bigint,
    objects_quarantined bigint,
    objects_failed bigint,
    rows_loaded bigint,
    rows_quarantined bigint,
    exit_code integer
);
create table if not exists schema_events (
    run_id varchar not null,
    object_key varchar not null,
    table_name varchar not null,
    kind varchar not null,
    reason_code varchar,
    added varchar,
    removed varchar,
    type_changes varchar,
    detected_at timestamp not null
);
create table if not exists backlog_items (
    table_name varchar not null,
    column_name varchar not null,
    first_seen_key varchar not null,
    first_seen_at timestamp not null,
    note varchar not null,
    primary key (table_name, column_name)
);
create table if not exists pending_full_refresh (
    table_name varchar primary key,
    reason varchar not null,
    requested_at timestamp not null
);
"""


@dataclass(frozen=True)
class ManifestRow:
    key: str
    etag: str
    status: ObjectStatus


@dataclass(frozen=True)
class ManifestDiff:
    new: tuple[SourceObject, ...] = field(default=())
    changed: tuple[SourceObject, ...] = field(default=())
    unchanged: tuple[SourceObject, ...] = field(default=())

    @property
    def to_fetch(self) -> tuple[SourceObject, ...]:
        return tuple(sorted(self.new + self.changed, key=lambda obj: obj.key))


def diff_objects(listed: Iterable[SourceObject], known: Iterable[ManifestRow]) -> ManifestDiff:
    """New keys, changed keys (another etag, or not settled yet), and unchanged keys."""
    by_key = {row.key: row for row in known}
    new: list[SourceObject] = []
    changed: list[SourceObject] = []
    unchanged: list[SourceObject] = []
    for obj in sorted(listed, key=lambda item: item.key):
        row = by_key.get(obj.key)
        if row is None:
            new.append(obj)
        elif row.etag != obj.etag or row.status not in SETTLED:
            changed.append(obj)
        else:
            unchanged.append(obj)
    return ManifestDiff(tuple(new), tuple(changed), tuple(unchanged))


@dataclass(frozen=True)
class ObjectRecord:
    obj: SourceObject
    table_name: str | None
    process_date: date | None
    status: ObjectStatus
    discovered_at: datetime
    source_label: str
    run_id: str
    contract_version: str
    loaded_at: datetime | None = None
    schema_hash: str | None = None
    row_count: int | None = None
    bronze_rows: int | None = None
    quarantined_rows: int | None = None
    error_code: str | None = None


class Manifest:
    """A thin, typed wrapper over the manifest database. Single writer: the ingestion runner."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._connection = duckdb.connect(str(path))
        self._connection.execute(_SCHEMA)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "Manifest":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def ensure_source(self, label: str) -> None:
        """Refuse to mix sources in one warehouse."""
        found = self._connection.execute("select distinct source_label from objects").fetchall()
        others = sorted(str(row[0]) for row in found if row[0] != label)
        if others:
            raise SourceMismatchError(
                f"this warehouse was built from {others[0]}; use another BANK_DATA_WAREHOUSE_DIR for {label}"
            )

    def known_rows(self) -> list[ManifestRow]:
        rows = self._connection.execute("select object_key, etag, status from objects").fetchall()
        return [ManifestRow(str(key), str(etag), ObjectStatus(str(status))) for key, etag, status in rows]

    def status_of(self, key: str) -> ObjectStatus | None:
        row = self._connection.execute("select status from objects where object_key = ?", [key]).fetchone()
        return None if row is None else ObjectStatus(str(row[0]))

    def upsert(self, record: ObjectRecord) -> None:
        obj = record.obj
        self._connection.execute(
            """
            insert or replace into objects values
            (?, ?, ?, ?, ?, ?, coalesce((select discovered_at from objects where object_key = ?), ?),
             ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                obj.key,
                record.table_name,
                record.process_date,
                obj.etag,
                obj.size,
                obj.last_modified,
                obj.key,
                record.discovered_at,
                record.loaded_at,
                record.status.value,
                record.schema_hash,
                record.row_count,
                record.bronze_rows,
                record.quarantined_rows,
                record.error_code,
                record.source_label,
                record.run_id,
                record.contract_version,
            ],
        )

    def outstanding_quarantined(self) -> list[tuple[str, str]]:
        """Whole batches still quarantined: ``(object_key, error_code)``."""
        rows = self._connection.execute(
            "select object_key, coalesce(error_code, '') from objects where status = ? order by object_key",
            [ObjectStatus.QUARANTINED.value],
        ).fetchall()
        return [(str(key), str(code)) for key, code in rows]

    def start_run(self, run_id: str, source_label: str, started_at: datetime, contract_version: str) -> None:
        self._connection.execute(
            "insert into runs (run_id, source_label, started_at, status, contract_version) values (?, ?, ?, ?, ?)",
            [run_id, source_label, started_at, "running", contract_version],
        )

    def finish_run(
        self, run_id: str, finished_at: datetime, status: str, exit_code: int, counts: dict[str, int]
    ) -> None:
        self._connection.execute(
            """
            update runs set finished_at = ?, status = ?, exit_code = ?, objects_listed = ?, objects_new = ?,
            objects_changed = ?, objects_unchanged = ?, objects_loaded = ?, objects_quarantined = ?,
            objects_failed = ?, rows_loaded = ?, rows_quarantined = ? where run_id = ?
            """,
            [
                finished_at,
                status,
                exit_code,
                counts.get("listed", 0),
                counts.get("new", 0),
                counts.get("changed", 0),
                counts.get("unchanged", 0),
                counts.get("loaded", 0),
                counts.get("quarantined", 0),
                counts.get("failed", 0),
                counts.get("rows_loaded", 0),
                counts.get("rows_quarantined", 0),
                run_id,
            ],
        )

    def record_schema_event(
        self,
        run_id: str,
        key: str,
        table: str,
        kind: str,
        reason_code: str | None,
        added: Sequence[str],
        removed: Sequence[str],
        type_changes: Sequence[str],
        detected_at: datetime,
    ) -> None:
        self._connection.execute(
            "insert into schema_events values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                run_id,
                key,
                table,
                kind,
                reason_code,
                ",".join(added),
                ",".join(removed),
                ",".join(type_changes),
                detected_at,
            ],
        )

    def record_backlog_item(self, table: str, column: str, key: str, seen_at: datetime) -> bool:
        """Record an additive column once; returns True when the item is new."""
        exists = self._connection.execute(
            "select 1 from backlog_items where table_name = ? and column_name = ?", [table, column]
        ).fetchone()
        if exists is not None:
            return False
        note = f"Additive column {table}.{column} arrived in bronze; decide whether the contract and silver adopt it"
        self._connection.execute(
            "insert into backlog_items values (?, ?, ?, ?, ?)", [table, column, key, seen_at, note]
        )
        return True

    def request_full_refresh(self, table: str, reason: str, at: datetime) -> None:
        self._connection.execute("insert or replace into pending_full_refresh values (?, ?, ?)", [table, reason, at])

    def pending_full_refresh(self) -> list[str]:
        rows = self._connection.execute("select table_name from pending_full_refresh order by table_name").fetchall()
        return [str(row[0]) for row in rows]

    def clear_full_refresh(self) -> None:
        self._connection.execute("delete from pending_full_refresh")
