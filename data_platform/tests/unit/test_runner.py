from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from bank_data.contracts.tables import table_spec
from bank_data.ingest.local import LocalSource
from bank_data.ingest.manifest import Manifest, ObjectStatus
from bank_data.ingest.runner import IngestRunner, manifest_etag_matches
from bank_data.ingest.source import SourceObject

SNAPSHOT = date(2026, 6, 17)
CLOCK = datetime(2026, 9, 26, 12, 0, tzinfo=UTC).replace(tzinfo=None)
RATE_HEADER = "date,source_currency,target_currency,exchange_rate,buy_rate,sell_rate,source\n"


def _rates(*rows: str) -> str:
    return "\ufeff" + RATE_HEADER + "".join(f"{row}\n" for row in rows)


def _runner(source_dir: Path, warehouse: Path) -> IngestRunner:
    return IngestRunner(LocalSource(source_dir), warehouse, snapshot_date=SNAPSHOT, workers=2, clock=lambda: CLOCK)


def test_ingest_is_incremental_idempotent_and_conserves_rows(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "daily_exchange_rates.csv").write_text(
        _rates("2024-01-01,COP,USD,0.00025,,,Reuters", "2024-01-01,EUR,USD,1.1,,,Reuters"), encoding="utf-8"
    )
    (source / "notes.txt").write_text("not data", encoding="utf-8")

    first = _runner(source, tmp_path / "wh").run()
    second = _runner(source, tmp_path / "wh").run()

    assert first.exit_code == 0
    assert (first.new, first.skipped) == (2, 1)
    loaded = next(outcome for outcome in first.outcomes if outcome.key == "daily_exchange_rates.csv")
    assert (loaded.row_count, loaded.bronze_rows, loaded.quarantined_rows) == (2, 1, 1)
    assert loaded.reasons == {"value_not_accepted": 1}
    assert (second.new, second.changed, second.unchanged, second.outcomes) == (0, 0, 2, ())
    for spec_name in ("customers", "transactions"):
        assert (tmp_path / "wh" / "bronze" / spec_name / "_empty.parquet").exists()
    with Manifest(tmp_path / "wh" / "manifest.duckdb") as manifest:
        assert manifest.status_of("notes.txt") is ObjectStatus.SKIPPED
        assert manifest.status_of("daily_exchange_rates.csv") is ObjectStatus.LOADED


def test_redelivery_that_drops_keys_requests_a_full_refresh(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    path = source / "daily_exchange_rates.csv"
    path.write_text(_rates("2024-01-01,COP,USD,0.00025,,,x", "2024-01-02,COP,USD,0.00026,,,x"), encoding="utf-8")
    _runner(source, tmp_path / "wh").run()

    path.write_text(_rates("2024-01-02,COP,USD,0.00027,,,x"), encoding="utf-8")
    report = _runner(source, tmp_path / "wh").run()

    assert report.changed == 1
    assert report.outcomes[0].removed_keys == 1
    with Manifest(tmp_path / "wh" / "manifest.duckdb") as manifest:
        assert manifest.pending_full_refresh() == ["daily_exchange_rates"]


def test_unreadable_and_removed_column_objects_are_quarantined(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "daily_exchange_rates.csv").write_text("date,source_currency\n2024-01-01,COP\n", encoding="utf-8")
    (source / "branches.csv").write_bytes(b"\x00\x01\x02 not a csv \xff\xfe")

    report = _runner(source, tmp_path / "wh").run()

    assert report.exit_code == 3
    codes = dict(report.outstanding_quarantined)
    assert codes["daily_exchange_rates.csv"] == "schema_removed_column"
    assert codes["branches.csv"].startswith("unreadable_object")


def test_download_failures_are_recorded_and_retried(tmp_path: Path) -> None:
    class FlakySource(LocalSource):
        fail = True

        def download(self, obj: SourceObject, destination: Path) -> None:
            if self.fail:
                raise OSError("disk unavailable")
            super().download(obj, destination)

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "daily_exchange_rates.csv").write_text(_rates("2024-01-01,COP,USD,0.00025,,,x"), encoding="utf-8")
    flaky = FlakySource(source_dir)
    runner = IngestRunner(flaky, tmp_path / "wh", snapshot_date=SNAPSHOT, clock=lambda: CLOCK)

    failed = runner.run()
    assert failed.exit_code == 1
    assert failed.outcomes[0].error_code == "download_failed:OSError"

    flaky.fail = False
    retried = IngestRunner(flaky, tmp_path / "wh", snapshot_date=SNAPSHOT, clock=lambda: CLOCK).run()
    assert (retried.changed, retried.exit_code) == (1, 0)


def test_download_only_stops_before_bronze(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "daily_exchange_rates.csv").write_text(_rates("2024-01-01,COP,USD,0.00025,,,x"), encoding="utf-8")

    report = _runner(source, tmp_path / "wh").run(download_only=True)

    assert report.download_only is True
    assert (tmp_path / "wh" / "raw" / "daily_exchange_rates.csv").exists()
    assert not (tmp_path / "wh" / "bronze").exists()
    with Manifest(tmp_path / "wh" / "manifest.duckdb") as manifest:
        assert manifest.status_of("daily_exchange_rates.csv") is ObjectStatus.DOWNLOADED
    loaded = _runner(source, tmp_path / "wh").run()
    assert loaded.changed == 1
    assert loaded.counts()["rows_loaded"] == 1


def test_existing_raw_files_are_reused_only_when_the_md5_matches(tmp_path: Path) -> None:
    path = tmp_path / "f.csv"
    path.write_text("abc", encoding="utf-8")
    listed = SourceObject("f.csv", "900150983cd24fb0d6963f7d28e17f72", 3, datetime(2026, 1, 1, tzinfo=UTC))
    assert manifest_etag_matches(path, listed) is True
    assert manifest_etag_matches(path, SourceObject("f.csv", "x", 3, listed.last_modified)) is False
    assert manifest_etag_matches(path, SourceObject("f.csv", "abc-2", 3, listed.last_modified)) is False


def test_unexpected_load_errors_mark_the_object_failed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "daily_exchange_rates.csv").write_text(_rates("2024-01-01,COP,USD,0.00025,,,x"), encoding="utf-8")
    runner = _runner(source, tmp_path / "wh")

    def explode(*_: object, **__: object) -> None:
        raise RuntimeError("bug")

    monkeypatch.setattr(runner, "_load_one", explode)
    report = runner.run()
    assert report.exit_code == 1
    assert report.outcomes[0].error_code == "load_failed:RuntimeError"
    assert table_spec("daily_exchange_rates").layout == "snapshot"
