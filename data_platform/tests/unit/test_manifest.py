from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from bank_data.errors import SourceMismatchError
from bank_data.ingest.manifest import Manifest, ManifestRow, ObjectRecord, ObjectStatus, diff_objects
from bank_data.ingest.source import SourceObject

WHEN = datetime(2026, 8, 31, 21, 0, tzinfo=UTC)
NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC).replace(tzinfo=None)


def _object(key: str, etag: str = "e1") -> SourceObject:
    return SourceObject(key=key, etag=etag, size=10, last_modified=WHEN)


def test_diff_separates_new_changed_and_unchanged_objects() -> None:
    listed = [_object("a.csv"), _object("b.csv", "e2"), _object("c.csv"), _object("d.csv")]
    known = [
        ManifestRow("b.csv", "e1", ObjectStatus.LOADED),
        ManifestRow("c.csv", "e1", ObjectStatus.QUARANTINED),
        ManifestRow("d.csv", "e1", ObjectStatus.FAILED),
        ManifestRow("gone.csv", "e1", ObjectStatus.LOADED),
    ]

    diff = diff_objects(listed, known)

    assert [obj.key for obj in diff.new] == ["a.csv"]
    assert [obj.key for obj in diff.changed] == ["b.csv", "d.csv"]
    assert [obj.key for obj in diff.unchanged] == ["c.csv"]
    assert [obj.key for obj in diff.to_fetch] == ["a.csv", "b.csv", "d.csv"]


def _record(obj: SourceObject, status: ObjectStatus, source: str = "local:test", **fields: object) -> ObjectRecord:
    return ObjectRecord(
        obj=obj,
        table_name="branches",
        process_date=date(2026, 6, 17),
        status=status,
        discovered_at=NOW,
        source_label=source,
        run_id="run-1",
        contract_version="1.0.0",
        **fields,  # type: ignore[arg-type]
    )


def test_manifest_records_objects_runs_events_and_refresh_requests(tmp_path: Path) -> None:
    with Manifest(tmp_path / "manifest.duckdb") as manifest:
        manifest.start_run("run-1", "local:test", NOW, "1.0.0")
        obj = _object("branches.csv")
        manifest.upsert(_record(obj, ObjectStatus.DOWNLOADED))
        manifest.upsert(_record(obj, ObjectStatus.LOADED, row_count=3, bronze_rows=3, quarantined_rows=0))
        manifest.upsert(_record(_object("x.csv"), ObjectStatus.QUARANTINED, error_code="schema_type_change"))
        manifest.record_schema_event(
            "run-1", "x.csv", "branches", "breaking", "schema_type_change", [], [], ["atm_count"], NOW
        )
        assert manifest.record_backlog_item("branches", "note", "x.csv", NOW) is True
        assert manifest.record_backlog_item("branches", "note", "y.csv", NOW) is False
        manifest.request_full_refresh("transactions", "keys removed", NOW)
        manifest.finish_run("run-1", NOW, "failed", 3, {"listed": 2, "loaded": 1})

        assert manifest.status_of("branches.csv") is ObjectStatus.LOADED
        assert manifest.status_of("missing.csv") is None
        assert {row.key: row.status for row in manifest.known_rows()} == {
            "branches.csv": ObjectStatus.LOADED,
            "x.csv": ObjectStatus.QUARANTINED,
        }
        assert manifest.outstanding_quarantined() == [("x.csv", "schema_type_change")]
        assert manifest.pending_full_refresh() == ["transactions"]
        manifest.clear_full_refresh()
        assert manifest.pending_full_refresh() == []


def test_manifest_refuses_a_second_source(tmp_path: Path) -> None:
    with Manifest(tmp_path / "manifest.duckdb") as manifest:
        manifest.upsert(_record(_object("branches.csv"), ObjectStatus.LOADED, source="s3"))
        manifest.ensure_source("s3")
        with pytest.raises(SourceMismatchError, match="built from s3"):
            manifest.ensure_source("local:data_platform/sample")
