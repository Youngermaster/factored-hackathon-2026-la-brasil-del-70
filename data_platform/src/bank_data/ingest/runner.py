"""The ingestion run: list, diff against the manifest, download, validate, and write bronze or quarantine.

Guarantees:

- **Incremental and idempotent.** Only new or changed objects (by etag) are downloaded and loaded; a second
  run over the same source changes nothing.
- **No silent drops.** Every row of a loaded object lands in exactly one of bronze or quarantine; the manifest
  records ``row_count = bronze_rows + quarantined_rows``.
- **Schema evolution.** Additive columns are accepted (warning plus backlog item); a removed column or a type
  change quarantines the whole batch and the run exits 3 (``SchemaEvolutionError``). The run keeps exiting 3
  while such a batch is outstanding, so nothing downstream builds over a missing partition unnoticed.
- **Re-deliveries.** A changed object replaces its bronze files. When the new version lacks primary keys the
  old one had, the table is marked for a full refresh, which ``bank-data build`` honors.
"""

import logging
import uuid
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from bank_data.contracts.evolution import (
    DEFAULT_TYPE_CHANGE_THRESHOLD,
    ChangeKind,
    SchemaChange,
    compare_columns,
    detect_type_changes,
    schema_hash,
)
from bank_data.contracts.tables import CONTRACT_VERSION, TABLES, TableSpec, table_spec
from bank_data.contracts.validation import parse_frame, validate_rows
from bank_data.errors import SchemaEvolutionError
from bank_data.ingest.bronze import BronzeStore, Lineage, UnreadableObjectError, read_raw, with_lineage, write_parquet
from bank_data.ingest.layout import ObjectLayout, parse_key
from bank_data.ingest.local import file_md5
from bank_data.ingest.manifest import Manifest, ObjectRecord, ObjectStatus, diff_objects
from bank_data.ingest.source import DataSource, SourceObject

LOGGER = logging.getLogger("bank_data.ingest")


def utc_now() -> datetime:
    """Naive UTC, the way timestamps are stored in Parquet and DuckDB ``timestamp`` columns."""
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class LoadOutcome:
    key: str
    status: ObjectStatus
    row_count: int = 0
    bronze_rows: int = 0
    quarantined_rows: int = 0
    schema_hash: str | None = None
    change: SchemaChange = field(default_factory=lambda: SchemaChange(ChangeKind.UNCHANGED))
    removed_keys: int = 0
    error_code: str | None = None
    reasons: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class IngestReport:
    run_id: str
    source_label: str
    listed: int
    new: int
    changed: int
    unchanged: int
    skipped: int
    outcomes: tuple[LoadOutcome, ...]
    outstanding_quarantined: tuple[tuple[str, str], ...]
    download_only: bool

    @property
    def exit_code(self) -> int:
        failed = any(outcome.status is ObjectStatus.FAILED for outcome in self.outcomes)
        if self.outstanding_quarantined:
            return SchemaEvolutionError.exit_code
        return 1 if failed else 0

    def counts(self) -> dict[str, int]:
        statuses = Counter(outcome.status for outcome in self.outcomes)
        return {
            "listed": self.listed,
            "new": self.new,
            "changed": self.changed,
            "unchanged": self.unchanged,
            "loaded": statuses[ObjectStatus.LOADED],
            "quarantined": statuses[ObjectStatus.QUARANTINED],
            "failed": statuses[ObjectStatus.FAILED],
            "rows_loaded": sum(outcome.bronze_rows for outcome in self.outcomes),
            "rows_quarantined": sum(outcome.quarantined_rows for outcome in self.outcomes),
        }


def load_object(
    key: str,
    etag: str,
    local_path: Path,
    layout: ObjectLayout,
    store: BronzeStore,
    *,
    run_id: str,
    loaded_at: datetime,
    type_change_threshold: float,
) -> LoadOutcome:
    """Validate one downloaded object and write its bronze and quarantine files. Thread-safe per key."""
    spec = table_spec(layout.table)
    try:
        raw = read_raw(local_path, layout.file_format)
    except UnreadableObjectError as error:
        return LoadOutcome(key, ObjectStatus.QUARANTINED, error_code=f"unreadable_object:{error}")
    observed = list(raw.columns)
    header_hash = schema_hash(observed)
    header_change = compare_columns(observed, spec)
    lineage = Lineage(key, etag, loaded_at, header_hash, run_id, layout.process_date)
    previous_keys = store.existing_keys(spec.name, layout.process_date, key, spec.primary_key)
    store.remove_object(spec.name, layout.process_date, key)

    if header_change.kind is ChangeKind.BREAKING:
        return _quarantine_batch(raw, spec, layout, store, lineage, header_change, key)
    parsed = parse_frame(raw, spec)
    change = detect_type_changes(header_change, parsed, threshold=type_change_threshold)
    if change.kind is ChangeKind.BREAKING:
        return _quarantine_batch(raw, spec, layout, store, lineage, change, key)

    partition = layout.process_date if layout.layout == "daily" else None
    result = validate_rows(raw[list(spec.column_names)], spec, partition_date=partition, parsed=parsed)
    enriched = with_lineage(raw, lineage)
    accepted = enriched[result.accepted.to_numpy()]
    rejected = enriched[(~result.accepted).to_numpy()].copy()
    if len(accepted) or not len(rejected):
        write_parquet(accepted, store.bronze_path(spec.name, layout.process_date, key))
    if len(rejected):
        rejected["_reason_code"] = result.reason[~result.accepted].astype("str").to_numpy()
        rejected["_column"] = result.column[~result.accepted].astype("str").to_numpy()
        write_parquet(rejected, store.quarantine_path(spec.name, layout.process_date, key))
    new_keys = {tuple(str(value) for value in row) for row in accepted[list(spec.primary_key)].itertuples(index=False)}
    reasons = result.reason[~result.accepted].value_counts().to_dict()
    return LoadOutcome(
        key,
        ObjectStatus.LOADED,
        row_count=len(raw),
        bronze_rows=len(accepted),
        quarantined_rows=len(rejected),
        schema_hash=header_hash,
        change=change,
        removed_keys=len(previous_keys - new_keys),
        reasons={str(code): int(count) for code, count in reasons.items()},
    )


def _quarantine_batch(
    raw: pd.DataFrame,
    spec: TableSpec,
    layout: ObjectLayout,
    store: BronzeStore,
    lineage: Lineage,
    change: SchemaChange,
    key: str,
) -> LoadOutcome:
    rejected = with_lineage(raw, lineage)
    code = change.reason_code or "schema_breaking_change"
    rejected["_reason_code"] = code
    rejected["_column"] = ",".join(change.removed or change.type_changes)
    write_parquet(rejected, store.quarantine_path(spec.name, layout.process_date, key))
    return LoadOutcome(
        key,
        ObjectStatus.QUARANTINED,
        row_count=len(raw),
        quarantined_rows=len(raw),
        schema_hash=lineage.schema_hash,
        change=change,
        error_code=code,
        reasons={code: len(raw)},
    )


class IngestRunner:
    def __init__(
        self,
        source: DataSource,
        warehouse_dir: Path,
        *,
        snapshot_date: date,
        workers: int = 4,
        type_change_threshold: float = DEFAULT_TYPE_CHANGE_THRESHOLD,
        clock: Callable[[], datetime] = utc_now,
        run_id: str | None = None,
    ) -> None:
        self._source = source
        self._warehouse = warehouse_dir
        self._raw_dir = warehouse_dir / "raw"
        self._store = BronzeStore(warehouse_dir)
        self._snapshot_date = snapshot_date
        self._workers = workers
        self._threshold = type_change_threshold
        self._clock = clock
        self._run_id = run_id or f"ingest-{uuid.uuid4().hex[:16]}"

    @property
    def manifest_path(self) -> Path:
        return self._warehouse / "manifest.duckdb"

    def run(self, *, download_only: bool = False) -> IngestReport:
        with Manifest(self.manifest_path) as manifest:
            manifest.ensure_source(self._source.label)
            started = self._clock()
            manifest.start_run(self._run_id, self._source.label, started, CONTRACT_VERSION)
            report = self._run(manifest, started, download_only=download_only)
            status = "succeeded" if report.exit_code == 0 else "failed"
            manifest.finish_run(self._run_id, self._clock(), status, report.exit_code, report.counts())
            return report

    def _record(
        self,
        manifest: Manifest,
        obj: SourceObject,
        layout: ObjectLayout | None,
        status: ObjectStatus,
        discovered: datetime,
        **fields: object,
    ) -> None:
        manifest.upsert(
            ObjectRecord(
                obj=obj,
                table_name=layout.table if layout else None,
                process_date=layout.process_date if layout else None,
                status=status,
                discovered_at=discovered,
                source_label=self._source.label,
                run_id=self._run_id,
                contract_version=CONTRACT_VERSION,
                **fields,  # type: ignore[arg-type]
            )
        )

    def _run(self, manifest: Manifest, started: datetime, *, download_only: bool) -> IngestReport:
        listed = list(self._source.list_objects())
        layouts = {
            obj.key: parse_key(obj.key, prefix=self._source.prefix, snapshot_date=self._snapshot_date) for obj in listed
        }
        diff = diff_objects(listed, manifest.known_rows())
        skipped = 0
        to_load: list[tuple[SourceObject, ObjectLayout]] = []
        for obj in diff.to_fetch:
            layout = layouts[obj.key]
            if layout is None:
                skipped += 1
                LOGGER.warning("skipping object with an unknown layout", extra={"object_key": obj.key})
                self._record(manifest, obj, None, ObjectStatus.SKIPPED, started, error_code="unknown_layout")
                continue
            to_load.append((obj, layout))

        downloaded = self._download_all(manifest, to_load, started)
        outcomes: list[LoadOutcome] = [
            outcome for outcome in downloaded if outcome is not None and outcome.status is ObjectStatus.FAILED
        ]
        ready = [(obj, layout) for (obj, layout), outcome in zip(to_load, downloaded, strict=True) if outcome is None]
        if not download_only:
            outcomes.extend(self._load_all(manifest, ready, started))
            for spec in TABLES:
                self._store.ensure_placeholder(spec)
        return IngestReport(
            run_id=self._run_id,
            source_label=self._source.label,
            listed=len(listed),
            new=len(diff.new),
            changed=len(diff.changed),
            unchanged=len(diff.unchanged),
            skipped=skipped,
            outcomes=tuple(outcomes),
            outstanding_quarantined=tuple(manifest.outstanding_quarantined()) if not download_only else (),
            download_only=download_only,
        )

    def raw_path(self, key: str) -> Path:
        return self._raw_dir / key

    def _download_all(
        self, manifest: Manifest, items: list[tuple[SourceObject, ObjectLayout]], started: datetime
    ) -> list[LoadOutcome | None]:
        def fetch(item: tuple[SourceObject, ObjectLayout]) -> LoadOutcome | None:
            obj, _ = item
            destination = self.raw_path(obj.key)
            if (
                destination.exists()
                and destination.stat().st_size == obj.size
                and manifest_etag_matches(destination, obj)
            ):
                return None
            try:
                self._source.download(obj, destination)
            except Exception as error:
                code = getattr(error, "code", type(error).__name__)
                return LoadOutcome(obj.key, ObjectStatus.FAILED, error_code=f"download_failed:{code}")
            return None

        with ThreadPoolExecutor(max_workers=self._workers) as pool:
            results = list(pool.map(fetch, items))
        for (obj, layout), outcome in zip(items, results, strict=True):
            if outcome is None:
                self._record(manifest, obj, layout, ObjectStatus.DOWNLOADED, started)
            else:
                LOGGER.error("download failed", extra={"object_key": obj.key, "error_code": outcome.error_code})
                self._record(manifest, obj, layout, ObjectStatus.FAILED, started, error_code=outcome.error_code)
        return results

    def _load_all(
        self, manifest: Manifest, items: list[tuple[SourceObject, ObjectLayout]], started: datetime
    ) -> list[LoadOutcome]:
        loaded_at = self._clock()

        def load(item: tuple[SourceObject, ObjectLayout]) -> LoadOutcome:
            obj, layout = item
            try:
                return self._load_one(obj, layout, loaded_at)
            except Exception as error:
                LOGGER.exception("loading failed", extra={"object_key": obj.key})
                return LoadOutcome(obj.key, ObjectStatus.FAILED, error_code=f"load_failed:{type(error).__name__}")

        with ThreadPoolExecutor(max_workers=self._workers) as pool:
            outcomes = list(pool.map(load, items))
        return self._record_loads(manifest, items, outcomes, started, loaded_at)

    def _load_one(self, obj: SourceObject, layout: ObjectLayout, loaded_at: datetime) -> LoadOutcome:
        return load_object(
            obj.key,
            obj.etag,
            self.raw_path(obj.key),
            layout,
            self._store,
            run_id=self._run_id,
            loaded_at=loaded_at,
            type_change_threshold=self._threshold,
        )

    def _record_loads(
        self,
        manifest: Manifest,
        items: list[tuple[SourceObject, ObjectLayout]],
        outcomes: list[LoadOutcome],
        started: datetime,
        loaded_at: datetime,
    ) -> list[LoadOutcome]:
        for (obj, layout), outcome in zip(items, outcomes, strict=True):
            self._record(
                manifest,
                obj,
                layout,
                outcome.status,
                started,
                loaded_at=loaded_at,
                schema_hash=outcome.schema_hash,
                row_count=outcome.row_count,
                bronze_rows=outcome.bronze_rows,
                quarantined_rows=outcome.quarantined_rows,
                error_code=outcome.error_code,
            )
            change = outcome.change
            if change.kind is not ChangeKind.UNCHANGED:
                manifest.record_schema_event(
                    self._run_id,
                    obj.key,
                    layout.table,
                    change.kind.value,
                    change.reason_code,
                    change.added,
                    change.removed,
                    change.type_changes,
                    loaded_at,
                )
            if change.kind is ChangeKind.ADDITIVE:
                LOGGER.warning(
                    "additive columns accepted into bronze as nullable strings",
                    extra={"object_key": obj.key, "columns": ",".join(change.added)},
                )
                for column in change.added:
                    manifest.record_backlog_item(layout.table, column, obj.key, loaded_at)
            if change.kind is ChangeKind.BREAKING:
                LOGGER.error(
                    "breaking schema change: batch quarantined",
                    extra={"object_key": obj.key, "reason_code": change.reason_code, "detail": change.describe()},
                )
            if outcome.removed_keys:
                manifest.request_full_refresh(
                    layout.table, f"re-delivery of {obj.key} removed {outcome.removed_keys} keys", loaded_at
                )
        return outcomes


def manifest_etag_matches(path: Path, obj: SourceObject) -> bool:
    """True when a raw file already on disk has the listed content (single-part MD5 etags only)."""
    if "-" in obj.etag:
        return False
    return file_md5(path) == obj.etag
