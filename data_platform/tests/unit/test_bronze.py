from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pandas as pd

from bank_data.contracts.tables import table_spec
from bank_data.ingest.bronze import (
    EMPTY_FILE_NAME,
    BronzeStore,
    Lineage,
    object_id,
    read_raw,
    with_lineage,
    write_parquet,
)

LINEAGE = Lineage(
    "data/branches.csv",
    "etag-1",
    datetime(2026, 9, 26, 12, 0, tzinfo=UTC).replace(tzinfo=None),
    "hash",
    "run-1",
    date(2026, 6, 17),
)


def test_read_raw_keeps_empty_strings_and_normalizes_headers(tmp_path: Path) -> None:
    path = tmp_path / "file.csv"
    path.write_text('\ufeffID ,Name\n1,\n2,"x, y"\n', encoding="utf-8")

    frame = read_raw(path, "csv")

    assert list(frame.columns) == ["id", "name"]
    assert frame.to_dict("list") == {"id": ["1", "2"], "name": ["", "x, y"]}


def test_lineage_columns_and_parquet_round_trip(tmp_path: Path) -> None:
    frame = pd.DataFrame({"branch_id": ["A", "B"], "note": ["", "z"]}, dtype="str")
    enriched = with_lineage(frame, LINEAGE)
    destination = tmp_path / "out" / "file.parquet"

    write_parquet(enriched, destination)

    rows = duckdb.execute(
        "select branch_id, note, _etag, _process_date, _source_row, typeof(_loaded_at) from read_parquet(?)",
        [destination.as_posix()],
    ).fetchall()
    assert rows == [
        ("A", "", "etag-1", date(2026, 6, 17), 1, "TIMESTAMP"),
        ("B", "z", "etag-1", date(2026, 6, 17), 2, "TIMESTAMP"),
    ]
    assert read_raw(destination, "parquet")["branch_id"].tolist() == ["A", "B"]


def test_store_replaces_an_objects_files_and_reports_its_keys(tmp_path: Path) -> None:
    store = BronzeStore(tmp_path)
    spec = table_spec("branches")
    bronze = store.bronze_path("branches", date(2026, 6, 17), "data/branches.csv")
    assert bronze.name == f"{object_id('data/branches.csv')}.parquet"
    write_parquet(with_lineage(pd.DataFrame({"branch_id": ["A", "B"]}, dtype="str"), LINEAGE), bronze)
    write_parquet(
        with_lineage(pd.DataFrame({"branch_id": ["C"]}, dtype="str"), LINEAGE),
        store.quarantine_path("branches", date(2026, 6, 17), "data/branches.csv"),
    )

    day = date(2026, 6, 17)
    assert store.existing_keys("branches", day, "data/branches.csv", spec.primary_key) == {("A",), ("B",)}
    store.remove_object("branches", day, "data/branches.csv")
    assert list(tmp_path.rglob("*.parquet")) == []
    assert store.existing_keys("branches", day, "data/branches.csv", spec.primary_key) == set()


def test_placeholder_gives_every_table_a_readable_empty_file(tmp_path: Path) -> None:
    store = BronzeStore(tmp_path)
    spec = table_spec("complaints")
    store.ensure_placeholder(spec)
    store.ensure_placeholder(spec)

    path = tmp_path / "bronze" / "complaints" / EMPTY_FILE_NAME
    relation = duckdb.execute("select * from read_parquet(?)", [path.as_posix()])
    assert relation.fetchall() == []
    columns = [column[0] for column in relation.description or ()]
    assert columns[: len(spec.column_names)] == list(spec.column_names)
    assert columns[-7:] == [
        "_source_key",
        "_etag",
        "_loaded_at",
        "_schema_hash",
        "_ingest_run_id",
        "_process_date",
        "_source_row",
    ]
