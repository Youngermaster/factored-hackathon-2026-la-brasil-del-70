"""The data-quality report (``docs/data/quality-report.md``), computed from the manifest, bronze, quarantine,
and the built warehouse.

Sections: run metadata (timestamp, git sha, source, dataset version, manifest summary), row counts per layer
next to the dictionary counts, duplicates removed, null rates per column against the dictionary's roughly 5%,
orphans and quarantine counts by reason, schema-evolution events and backlog items, freshness against the
configured thresholds, and the contact-reason distribution that phase 04 builds on.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import duckdb

from bank_data.config import SourceConfig
from bank_data.contracts.tables import TABLES, TableSpec

EXPECTED_NULL_RATE = 0.05
_NULL_BAND = (0.02, 0.08)
"""Null rates inside this band read as the dictionary's random ~5%; outside it, as structural."""


@dataclass
class TableCounts:
    table: str
    dictionary_rows: int
    objects: int = 0
    raw_rows: int = 0
    bronze_rows: int = 0
    quarantined_rows: int = 0
    exact_duplicates: int = 0
    key_duplicates: int = 0
    silver_rows: int = 0


@dataclass
class QualityData:
    generated_at: datetime
    git_sha: str
    source_label: str
    dataset_version: str
    snapshot_date: str
    runs: list[tuple[str, str, str, int, int, int]]
    counts: list[TableCounts]
    gold_counts: list[tuple[str, int]]
    null_rates: dict[str, list[tuple[str, bool, float]]]
    quarantine: list[tuple[str, str, str, int]]
    orphans: list[tuple[str, str, str, int, int]]
    schema_events: list[tuple[str, str, str, str]]
    backlog: list[tuple[str, str, str]]
    freshness: list[tuple[str, str, float, int, int, str]]
    contact_reasons: list[tuple[str, str, int, float, float]]
    foreign_references: list[tuple[str, str, int, int]] = field(default_factory=list)


def _one(connection: duckdb.DuckDBPyConnection, sql: str, parameters: Sequence[object] = ()) -> int:
    row = connection.execute(sql, list(parameters)).fetchone()
    return 0 if row is None or row[0] is None else int(row[0])


def _bronze_glob(bronze_dir: Path, table: str) -> str:
    return (bronze_dir / table / "**" / "*.parquet").as_posix()


def collect(
    warehouse_dir: Path,
    warehouse_db: Path,
    config: SourceConfig,
    *,
    generated_at: datetime,
    git_sha: str,
) -> QualityData:
    manifest = duckdb.connect(str(warehouse_dir / "manifest.duckdb"), read_only=True)
    try:
        source_label = str((manifest.execute("select any_value(source_label) from objects").fetchone() or ("",))[0])
        runs = [
            (str(run_id), str(started), str(status), int(listed or 0), int(loaded or 0), int(quarantined or 0))
            for run_id, started, status, listed, loaded, quarantined in manifest.execute(
                "select run_id, cast(started_at as varchar), status, objects_listed, rows_loaded, rows_quarantined "
                "from runs order by started_at desc limit 5"
            ).fetchall()
        ]
        per_table = {
            str(table): (int(objects), int(raw or 0), int(bronze or 0), int(quarantined or 0))
            for table, objects, raw, bronze, quarantined in manifest.execute(
                "select table_name, count(*), sum(row_count), sum(bronze_rows), sum(quarantined_rows) from objects "
                "where table_name is not null group by 1"
            ).fetchall()
        }
        schema_events = [
            (str(table), str(kind), str(reason or ""), f"{added or ''} {removed or ''} {changes or ''}".strip())
            for table, kind, reason, added, removed, changes in manifest.execute(
                "select table_name, kind, reason_code, added, removed, type_changes from schema_events "
                "order by detected_at, object_key"
            ).fetchall()
        ]
        backlog = [
            (str(table), str(column), str(note))
            for table, column, note in manifest.execute(
                "select table_name, column_name, note from backlog_items order by 1, 2"
            ).fetchall()
        ]
    finally:
        manifest.close()

    bronze_dir = warehouse_dir / "bronze"
    quarantine_dir = warehouse_dir / "quarantine"
    connection = duckdb.connect(str(warehouse_db), read_only=True)
    try:
        counts: list[TableCounts] = []
        freshness: list[tuple[str, str, float, int, int, str]] = []
        for spec in TABLES:
            objects, raw, bronze, quarantined = per_table.get(spec.name, (0, 0, 0, 0))
            item = TableCounts(spec.name, spec.dictionary_rows, objects, raw, bronze, quarantined)
            item.exact_duplicates, item.key_duplicates = _duplicates(connection, bronze_dir, spec)
            item.silver_rows = _one(connection, f"select count(*) from silver.stg_{spec.name}")  # noqa: S608
            counts.append(item)
            freshness.append(_freshness(connection, bronze_dir, spec, config, generated_at))
        null_rates = {spec.name: _null_rates(connection, spec) for spec in TABLES}
        gold_counts = [
            (str(name), _one(connection, f"select count(*) from gold.{name}"))  # noqa: S608
            for (name,) in connection.execute(
                "select table_name from information_schema.tables where table_schema = 'gold' order by 1"
            ).fetchall()
        ]
        orphans = _orphans(connection)
        quarantine = _quarantine(connection, quarantine_dir)
        contact_reasons = _contact_reasons(connection)
        foreign_references = [
            (
                table,
                column,
                _one(connection, f"select count(*) from silver.silver_{table} where {flag}"),  # noqa: S608
                _one(connection, f'select count("{column}") from silver.silver_{table}'),  # noqa: S608
            )
            for table, column, flag in (
                ("complaints", "affected_product_id", "has_foreign_affected_product"),
                ("digital_events", "product_id", "has_foreign_product"),
            )
        ]
    finally:
        connection.close()
    return QualityData(
        generated_at=generated_at,
        git_sha=git_sha,
        source_label=source_label,
        dataset_version=config.dataset.version,
        snapshot_date=config.dataset.snapshot_date.isoformat(),
        runs=runs,
        counts=counts,
        gold_counts=gold_counts,
        null_rates=null_rates,
        quarantine=quarantine,
        orphans=orphans,
        schema_events=schema_events,
        backlog=backlog,
        freshness=freshness,
        contact_reasons=contact_reasons,
        foreign_references=foreign_references,
    )


def _duplicates(connection: duckdb.DuckDBPyConnection, bronze_dir: Path, spec: TableSpec) -> tuple[int, int]:
    data = ", ".join(f'"{name}"' for name in spec.column_names)
    keys = ", ".join(f'trim("{name}")' for name in spec.primary_key)
    row = connection.execute(
        f"select count(*), count(distinct ({data})), count(distinct ({keys})) "  # noqa: S608 (spec names)
        "from read_parquet(?, union_by_name = true)",
        [_bronze_glob(bronze_dir, spec.name)],
    ).fetchone() or (0, 0, 0)
    total, distinct_rows, distinct_keys = (int(value or 0) for value in row)
    return total - distinct_rows, distinct_rows - distinct_keys


def _null_rates(connection: duckdb.DuckDBPyConnection, spec: TableSpec) -> list[tuple[str, bool, float]]:
    columns = spec.silver_columns
    expressions = ", ".join(f'count("{column.name}")' for column in columns)
    row = connection.execute(f"select count(*), {expressions} from silver.stg_{spec.name}").fetchone()  # noqa: S608
    if row is None or not row[0]:
        return [(column.name, column.nullable, 0.0) for column in columns]
    total = int(row[0])
    return [
        (column.name, column.nullable, 1 - int(value) / total) for column, value in zip(columns, row[1:], strict=True)
    ]


def _freshness(
    connection: duckdb.DuckDBPyConnection, bronze_dir: Path, spec: TableSpec, config: SourceConfig, now: datetime
) -> tuple[str, str, float, int, int, str]:
    latest = connection.execute(
        "select cast(max(_loaded_at) as varchar) from read_parquet(?, union_by_name = true)",
        [_bronze_glob(bronze_dir, spec.name)],
    ).fetchone()
    thresholds = config.freshness.for_table(spec.name)
    if latest is None or latest[0] is None:
        return (
            spec.name,
            "never loaded",
            float("inf"),
            thresholds.warn_after_hours,
            thresholds.error_after_hours,
            "error",
        )
    loaded = datetime.fromisoformat(str(latest[0]))
    age = (now.replace(tzinfo=None) - loaded).total_seconds() / 3600
    status = "pass"
    if age > thresholds.error_after_hours:
        status = "error"
    elif age > thresholds.warn_after_hours:
        status = "warn"
    return (spec.name, str(latest[0])[:19], age, thresholds.warn_after_hours, thresholds.error_after_hours, status)


def _orphans(connection: duckdb.DuckDBPyConnection) -> list[tuple[str, str, str, int, int]]:
    found = {
        (str(table), str(column)): (str(parent), int(count))
        for table, column, parent, count in connection.execute(
            "select table_name, fk_column, referenced_table, count(*) from silver.quarantine_orphans group by all"
        ).fetchall()
    }
    rows: list[tuple[str, str, str, int, int]] = []
    for spec in TABLES:
        for column in spec.foreign_keys:
            parent = column.references[0] if column.references else ""
            total = _one(
                connection,
                f'select count("{column.name}") from silver.stg_{spec.name}',  # noqa: S608 (spec names)
            )
            rows.append((spec.name, column.name, parent, found.get((spec.name, column.name), ("", 0))[1], total))
    return rows


def _quarantine(connection: duckdb.DuckDBPyConnection, quarantine_dir: Path) -> list[tuple[str, str, str, int]]:
    rows: list[tuple[str, str, str, int]] = []
    for spec in TABLES:
        files = sorted((quarantine_dir / spec.name).glob("**/*.parquet"))
        if not files:
            continue
        rows.extend(
            (spec.name, str(reason), str(column), int(count))
            for reason, column, count in connection.execute(
                "select _reason_code, _column, count(*) from read_parquet(?, union_by_name = true) group by all "
                "order by 3 desc, 1, 2",
                [[path.as_posix() for path in files]],
            ).fetchall()
        )
    return rows


def _contact_reasons(connection: duckdb.DuckDBPyConnection) -> list[tuple[str, str, int, float, float]]:
    return [
        (str(reason), str(category), int(count), float(resolved or 0), float(escalated or 0))
        for reason, category, count, resolved, escalated in connection.execute(
            "select contact_reason, reason_category, sum(interactions), sum(resolved) / sum(interactions), "
            "sum(escalated) / sum(interactions) from gold.contact_reason_daily group by all order by 3 desc"
        ).fetchall()
    ]


def _percent(value: float) -> str:
    return f"{100 * value:.2f}%"


def render(data: QualityData) -> str:
    lines = [
        "# Data quality report",
        "",
        f"Generated by `make data-report` at {data.generated_at.isoformat(timespec='seconds')} from commit "
        f"`{data.git_sha}`. Source: `{data.source_label}`; delivery `{data.dataset_version}`; snapshot date "
        f"{data.snapshot_date}. Do not edit by hand.",
        "",
        "## Manifest summary",
        "",
        "| Run | Started (UTC) | Status | Objects listed | Rows loaded | Rows quarantined |",
        "|---|---|---|---|---|---|",
        *(
            f"| `{run}` | {started[:19]} | {status} | {listed:,} | {loaded:,} | {quarantined:,} |"
            for run, started, status, listed, loaded, quarantined in data.runs
        ),
        "",
        "Rows loaded and quarantined count the objects each run processed; an unchanged object is not reprocessed.",
        "",
        "## Row counts per layer",
        "",
        "| Table | Dictionary | Objects | Raw rows | Bronze | Quarantined | Exact duplicates | Key duplicates "
        "| Silver |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for item in data.counts:
        lines.append(
            f"| {item.table} | {item.dictionary_rows:,} | {item.objects:,} | {item.raw_rows:,} "
            f"| {item.bronze_rows:,} | "
            f"{item.quarantined_rows:,} | {item.exact_duplicates:,} | {item.key_duplicates:,} | {item.silver_rows:,} |"
        )
    removed = sum(item.bronze_rows - item.silver_rows for item in data.counts)
    lines += [
        "",
        f"Duplicates removed between bronze and silver: {removed:,} rows. Every raw row is in exactly one of bronze "
        "or quarantine (raw rows = bronze + quarantined).",
        "",
        "| Gold relation | Rows |",
        "|---|---|",
        *(f"| {name} | {count:,} |" for name, count in data.gold_counts),
        "",
        "## Null rates",
        "",
        f"Share of null values per silver column after empty-string normalization. The dictionary announces about "
        f"{_percent(EXPECTED_NULL_RATE)} nulls in nullable fields; rates outside {_percent(_NULL_BAND[0])} to "
        f"{_percent(_NULL_BAND[1])} are marked structural (the column is empty by design for some rows, for "
        "example `amount_usd` on USD transactions or `merchant_name` outside purchases). Required columns are "
        "never null after the contract; columns without nulls are not listed.",
        "",
        "| Table | Column | Nullable | Null rate | Reading |",
        "|---|---|---|---|---|",
    ]
    for table, rates in data.null_rates.items():
        for column, nullable, rate in rates:
            if rate == 0:
                continue
            reading = "none" if rate == 0 else ("about 5%" if _NULL_BAND[0] <= rate <= _NULL_BAND[1] else "structural")
            lines.append(f"| {table} | {column} | {'yes' if nullable else 'no'} | {_percent(rate)} | {reading} |")
    lines += [
        "",
        "## Orphans",
        "",
        "Foreign keys whose parent row is missing. Orphans stay in silver, flagged (`is_orphan_<column>`), and are "
        "listed by `silver.quarantine_orphans`; serving tables leave them out where a record could not be served.",
        "",
        "| Table | Column | Parent | Orphans | Non-null values | Share |",
        "|---|---|---|---|---|---|",
        *(
            f"| {table} | {column} | {parent} | {count:,} | {total:,} "
            f"| {f'{100 * count / total:.3f}%' if total else '0.000%'} |"
            for table, column, parent, count, total in data.orphans
        ),
        "",
        "Cross-customer references: a product reference that resolves, but to another customer's product.",
        "",
        "| Table | Column | Other customer's product | Non-null values |",
        "|---|---|---|---|",
        *(f"| {table} | {column} | {count:,} | {total:,} |" for table, column, count, total in data.foreign_references),
        "",
        "## Quarantine",
        "",
    ]
    if data.quarantine:
        lines += [
            "| Table | Reason | Column | Rows |",
            "|---|---|---|---|",
            *(f"| {table} | {reason} | {column} | {count:,} |" for table, reason, column, count in data.quarantine),
        ]
    else:
        lines.append("No row is quarantined.")
    lines += ["", "## Schema evolution", ""]
    if data.schema_events:
        lines += [
            "| Table | Kind | Reason | Columns |",
            "|---|---|---|---|",
            *(f"| {table} | {kind} | {reason} | {columns} |" for table, kind, reason, columns in data.schema_events),
        ]
    else:
        lines.append("No schema-evolution event: every object carries exactly the contract columns.")
    if data.backlog:
        lines += ["", "Backlog items recorded for additive columns:", ""]
        lines += [f"- `{table}.{column}`: {note}" for table, column, note in data.backlog]
    lines += [
        "",
        "## Freshness",
        "",
        "Hours since the latest `_loaded_at` of each bronze table, against the prototype thresholds in "
        "`data_platform/config/sources.yml` (the same thresholds `dbt source freshness` uses).",
        "",
        "| Table | Last loaded (UTC) | Age (hours) | Warn after | Error after | Status |",
        "|---|---|---|---|---|---|",
        *(
            f"| {table} | {loaded} | {age:.1f} | {warn} | {error} | {status} |"
            for table, loaded, age, warn, error, status in data.freshness
        ),
        "",
        "## Contact reasons",
        "",
        "The distribution phase 04 maps to the four workflows (from `gold.contact_reason_daily`).",
        "",
        "| Contact reason | Category | Interactions | Share | Resolved | Escalated |",
        "|---|---|---|---|---|---|",
    ]
    total_contacts = sum(count for _, _, count, _, _ in data.contact_reasons) or 1
    lines += [
        f"| {reason} | {category} | {count:,} | {_percent(count / total_contacts)} | {_percent(resolved)} "
        f"| {_percent(escalated)} |"
        for reason, category, count, resolved, escalated in data.contact_reasons
    ]
    lines += [""]
    return "\n".join(lines)
