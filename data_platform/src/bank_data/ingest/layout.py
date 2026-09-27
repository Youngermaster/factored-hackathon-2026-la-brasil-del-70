"""Table membership and partition from an object key.

The organizer bucket has two layouts under the prefix (documented in ``docs/data/source-layout.md``):

- ``<table>.csv``: a full or monthly snapshot of a dimension or reference table;
- ``<table>/year=YYYY/month=MM/day=DD/<table>_YYYYMMDD.csv``: one daily partition of a fact table.

Parquet files with the same names are accepted as well. Any other key is not a data object of a known
table and is skipped (recorded in the manifest with ``unknown_layout``).
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import Literal

from bank_data.contracts.tables import TABLES_BY_NAME, Layout

FileFormat = Literal["csv", "parquet"]

_SNAPSHOT = re.compile(r"^(?P<table>[a-z][a-z0-9_]*)\.(?P<format>csv|parquet)$")
_DAILY = re.compile(
    r"^(?P<table>[a-z][a-z0-9_]*)/year=(?P<year>\d{4})/month=(?P<month>\d{2})/day=(?P<day>\d{2})/"
    r"(?P<file>[^/]+)\.(?P<format>csv|parquet)$"
)


@dataclass(frozen=True)
class ObjectLayout:
    table: str
    layout: Layout
    process_date: date
    """The partition date (the dataset snapshot date for snapshot objects)."""
    file_format: FileFormat


def relative_key(key: str, prefix: str) -> str | None:
    """The key without the source prefix, or ``None`` when the key lies outside it."""
    if prefix and not key.startswith(prefix):
        return None
    return key[len(prefix) :]


def parse_key(key: str, *, prefix: str, snapshot_date: date) -> ObjectLayout | None:
    """Parse ``key``; ``None`` for keys of no known table or with a layout the table does not use."""
    relative = relative_key(key, prefix)
    if relative is None:
        return None
    snapshot = _SNAPSHOT.match(relative)
    if snapshot is not None:
        table = snapshot["table"]
        spec = TABLES_BY_NAME.get(table)
        if spec is None or spec.layout != "snapshot":
            return None
        return ObjectLayout(table, "snapshot", snapshot_date, "csv" if snapshot["format"] == "csv" else "parquet")
    daily = _DAILY.match(relative)
    if daily is None:
        return None
    table = daily["table"]
    spec = TABLES_BY_NAME.get(table)
    if spec is None or spec.layout != "daily":
        return None
    try:
        partition = date(int(daily["year"]), int(daily["month"]), int(daily["day"]))
    except ValueError:
        return None
    return ObjectLayout(table, "daily", partition, "csv" if daily["format"] == "csv" else "parquet")
