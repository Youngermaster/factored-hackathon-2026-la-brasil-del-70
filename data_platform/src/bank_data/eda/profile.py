"""Strict CSV ingestion, column profiling and semantic checks over all local rows."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from bank_data.eda.core import (
    CATEGORIES,
    connect,
    fields,
    keys,
    literal,
    phase,
    present,
    qi,
    records,
    require,
    write_json,
)
from bank_data.eda.inventory import verify_inputs


def dtype(column: dict[str, Any]) -> str:
    value = str(column["type"])
    return "VARCHAR" if value.startswith("VARCHAR") or value == "TEXT" else value


def ingest_file(connection: Any, manifest: dict[str, Any], entry: dict[str, Any], columns: list[str]) -> None:
    table, headers = entry["table"], entry["columns"]
    if not headers or len(set(headers)) != len(headers):
        raise ValueError("Invalid header")
    for header in headers:
        qi(header)
        if header.startswith("_"):
            raise ValueError("Reserved provenance column")
    projections = [qi(col) if col in headers else f"NULL::VARCHAR AS {qi(col)}" for col in columns]
    payload = ", ".join(qi(col) for col in columns)
    path = str(Path(manifest["source"]) / entry["path"])
    query = (
        f"INSERT INTO raw.{qi(table)} SELECT *, sha256(to_json(list_value({payload}))) FROM "  # noqa: S608 - validated identifiers and escaped file paths
        f"(SELECT {', '.join(projections)}, {literal(entry['path'])} AS _source_file, "
        f"row_number() OVER () AS _source_row FROM read_csv({literal(path)}, "
        "header=true, all_varchar=true, parallel=false, delim=',', quote='\"', escape='\"', "
        "strict_mode=true, null_padding=false, ignore_errors=false, max_line_size=16777216))"
    )
    inserted = connection.execute(query).fetchone()[0]
    connection.execute(
        "INSERT INTO meta.ingested_files VALUES (?, ?, ?, ?, ?)",
        [table, entry["path"], inserted, None, entry["partition_date"]],
    )


def ingest_batch(connection: Any, manifest: dict[str, Any], entries: list[dict[str, Any]], columns: list[str]) -> None:
    import duckdb

    connection.execute("BEGIN")
    try:
        for entry in entries:
            ingest_file(connection, manifest, entry, columns)
        connection.execute("COMMIT")
    except (duckdb.InvalidInputException, duckdb.ConversionException, ValueError):
        connection.execute("ROLLBACK")
        # Retry the entire rolled-back batch individually to isolate malformed files.
        for entry in entries:
            connection.execute("BEGIN")
            try:
                ingest_file(connection, manifest, entry, columns)
                connection.execute("COMMIT")
            except (duckdb.InvalidInputException, duckdb.ConversionException, ValueError) as error:
                connection.execute("ROLLBACK")
                connection.execute(
                    "INSERT INTO meta.ingested_files VALUES (?, ?, ?, ?, ?)",
                    [entry["table"], entry["path"], None, type(error).__name__, entry["partition_date"]],
                )


def ingest(connection: Any, manifest: dict[str, Any], run: Path) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in manifest["files"]:
        groups[entry["table"]].append(entry)
    connection.execute("CREATE SCHEMA IF NOT EXISTS raw")
    connection.execute("CREATE SCHEMA IF NOT EXISTS typed")
    connection.execute("CREATE SCHEMA IF NOT EXISTS meta")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS meta.ingested_files "
        "(table_name VARCHAR, file_path VARCHAR PRIMARY KEY, row_count BIGINT, "
        "error_type VARCHAR, partition_date VARCHAR)"
    )
    completed = {row[0] for row in connection.execute("SELECT file_path FROM meta.ingested_files").fetchall()}
    # Single-threaded CSV scans give source ordinals their original record order.
    connection.execute("SET threads=1")
    for table, entries in groups.items():
        columns = [column["name"] for column in fields(table)]
        for entry in entries:
            for header in entry["columns"]:
                try:
                    qi(header)
                except ValueError:
                    continue
                if not header.startswith("_") and header not in columns:
                    columns.append(header)
        definition = ", ".join(f"{qi(col)} VARCHAR" for col in columns)
        connection.execute(
            f"CREATE TABLE IF NOT EXISTS raw.{qi(table)} "
            f"({definition}, _source_file VARCHAR, _source_row BIGINT, _row_hash VARCHAR)"
        )
        pending = [entry for entry in entries if entry["path"] not in completed]
        for index in range(0, len(pending), 32):
            batch = pending[index : index + 32]
            ingest_batch(connection, manifest, batch, columns)
            completed.update(entry["path"] for entry in batch)
            write_json(
                run / "ingestion_progress.json",
                {
                    "current_table": table,
                    "files_finished": len(completed),
                    "files_total": len(manifest["files"]),
                    "tables_finished": list(groups)[: list(groups).index(table)],
                },
            )
        expressions = [
            f"TRY_CAST(NULLIF(trim({qi(c['name'])}), '') AS {dtype(c)}) AS {qi(c['name'])}"
            if dtype(c) != "VARCHAR"
            else qi(c["name"])
            for c in fields(table)
        ]
        connection.execute(
            f"CREATE OR REPLACE VIEW typed.{qi(table)} AS SELECT {', '.join(expressions)}, "  # noqa: S608 - validated identifiers
            f"_source_file, _source_row, _row_hash FROM raw.{qi(table)}"
        )
    connection.execute("SET threads=2")
    counts = records(
        connection,
        'SELECT table_name AS "table", file_path AS file, row_count AS rows, '
        "partition_date FROM meta.ingested_files WHERE error_type IS NULL ORDER BY file_path",
    )
    errors = records(
        connection,
        'SELECT table_name AS "table", file_path AS file, error_type '
        "FROM meta.ingested_files WHERE error_type IS NOT NULL ORDER BY file_path",
    )
    write_json(run / "file_counts.json", counts)
    write_json(
        run / "ingestion_progress.json",
        {
            "tables_finished": list(groups),
            "files_finished": len(completed),
            "files_total": len(manifest["files"]),
            "file_errors": len(errors),
        },
    )
    return errors


def semantic_rules(table: str) -> list[tuple[str, str, str]]:
    rules: list[tuple[str, str, str]] = []
    names = {c["name"] for c in fields(table)}
    for name in ["duration_seconds", "wait_time_seconds", "resolution_days", "days_past_due", "response_time_hours"]:
        if name in names:
            rules.append((f"{name}_nonnegative", f"{qi(name)} < 0", f"{qi(name)} IS NOT NULL"))
    ranges = {
        "credit_score": (300, 850),
        "sentiment_score": (-1, 1),
        "accent_confidence": (0, 1),
        "fraud_score": (0, 100),
        "resolution_satisfaction": (1, 5),
        "latitude": (-90, 90),
        "longitude": (-180, 180),
    }
    for name, (low, high) in ranges.items():
        if name in names:
            rules.append((f"{name}_range", f"{qi(name)} NOT BETWEEN {low} AND {high}", f"{qi(name)} IS NOT NULL"))
    if table == "daily_exchange_rates":
        rules.append(("positive_exchange_rate", "exchange_rate <= 0", "exchange_rate IS NOT NULL"))
    if table == "satisfaction_surveys":
        for kind, low, high in [("CSAT", 1, 5), ("NPS", 0, 10)]:
            eligible = f"survey_type='{kind}' AND main_score IS NOT NULL"
            rules.append((f"{kind}_score_range", f"({eligible}) AND main_score NOT BETWEEN {low} AND {high}", eligible))
    pairs = {
        "complaints": [
            ("creation_date", "assignment_date"),
            ("creation_date", "first_response_date"),
            ("creation_date", "resolution_date"),
            ("resolution_date", "closing_date"),
        ],
        "campaign_sends": [("send_date", "open_date"), ("send_date", "click_date"), ("send_date", "conversion_date")],
        "products": [("opening_date", "expiration_date")],
        "marketing_campaigns": [("start_date", "end_date")],
    }
    for start, end in pairs.get(table, []):
        rules.append(
            (f"{end}_after_{start}", f"{qi(end)} < {qi(start)}", f"{qi(end)} IS NOT NULL AND {qi(start)} IS NOT NULL")
        )
    if table == "complaints":
        rules.extend(
            [
                (
                    "resolved_without_date",
                    "status IN ('Resolved','Closed') AND resolution_date IS NULL",
                    "status IN ('Resolved','Closed')",
                ),
                (
                    "claimed_amount_without_currency",
                    "claimed_amount IS NOT NULL AND currency IS NULL",
                    "claimed_amount IS NOT NULL",
                ),
            ]
        )
    if table == "call_transcripts":
        rules.append(
            (
                "invalid_entities_json",
                "mentioned_entities IS NOT NULL AND NOT json_valid(mentioned_entities)",
                "mentioned_entities IS NOT NULL",
            )
        )
    if "process_date" in names:
        rules.append(
            (
                "partition_date_mismatch",
                "process_date != try_cast(regexp_extract(_source_file, "
                "'year=([0-9]+)/month=([0-9]+)/day=([0-9]+)', 1) || '-' || "
                "regexp_extract(_source_file, 'month=([0-9]+)', 1) || '-' || "
                "regexp_extract(_source_file, 'day=([0-9]+)', 1) AS DATE)",
                "process_date IS NOT NULL",
            )
        )
    return rules


def profile(run: Path) -> None:
    require(run, "inventory")
    with phase(run, "profile"):
        manifest = verify_inputs(run)
        connection = connect(run)
        try:
            errors = ingest(connection, manifest, run)
            tables: list[dict[str, Any]] = []
            columns: list[dict[str, Any]] = []
            checks: list[dict[str, Any]] = []
            categories: list[dict[str, Any]] = []
            available = sorted({entry["table"] for entry in manifest["files"]})
            for table in available:
                raw, typed = f"raw.{qi(table)}", f"typed.{qi(table)}"
                key = ", ".join(qi(k) for k in keys(table))
                summary = records(
                    connection,
                    f"SELECT count(*) AS rows, count(DISTINCT _row_hash) AS distinct_rows, "  # noqa: S608 - contract identifiers and escaped literals only
                    f"count(DISTINCT ({key})) AS distinct_keys FROM {raw}",
                )[0]
                summary.update(table=table)
                tables.append(summary)
                for col in fields(table):
                    name, kind = qi(col["name"]), dtype(col)
                    metrics = records(
                        connection,
                        f"SELECT count(*) AS denominator, "  # noqa: S608 - contract identifiers and escaped literals only
                        f"count(*) FILTER (WHERE NOT ({present(name)})) AS missing, "
                        f"count(DISTINCT {name}) AS distinct_values, "
                        f"count(*) FILTER (WHERE {present(name)} AND "
                        f"TRY_CAST(NULLIF(trim({name}), '') AS {kind}) IS NULL) AS invalid_type "
                        f"FROM {raw}",
                    )[0]
                    metrics.update(
                        table=table,
                        column=col["name"],
                        expected_type=kind,
                        required=col["required"],
                        severity="error" if col["required"] else "informational",
                    )
                    if kind not in {"VARCHAR", "BOOLEAN"}:
                        metrics.update(
                            records(connection, f"SELECT min({name}) AS minimum, max({name}) AS maximum FROM {typed}")[  # noqa: S608 - contract identifiers and escaped literals only
                                0
                            ]
                        )
                    if kind.startswith(("DECIMAL", "INTEGER")):
                        metrics.update(
                            records(
                                connection,
                                f"SELECT quantile_cont({name}, 0.5) AS median, "  # noqa: S608 - contract identifiers and escaped literals only
                                f"quantile_cont({name}, 0.95) AS p95 FROM {typed}",
                            )[0]
                        )
                    columns.append(metrics)
                    if col["unique"]:
                        checks.extend(
                            {"table": table, "rule": col["name"] + "_unique", "severity": "error", **row}
                            for row in records(
                                connection,
                                f"SELECT count({name}) - count(DISTINCT {name}) "  # noqa: S608 - contract identifiers and escaped literals only
                                f"AS violations, count({name}) AS denominator FROM {raw}",
                            )
                        )
                    if col["name"] in CATEGORIES:
                        categories.extend(
                            {"table": table, "column": col["name"], **row}
                            for row in records(
                                connection,
                                f"SELECT coalesce(cast({name} AS VARCHAR), '[missing]') AS value, count(*) AS rows "  # noqa: S608 - contract identifiers and escaped literals only
                                f"FROM {typed} GROUP BY 1 ORDER BY rows DESC, value LIMIT 100",
                            )
                        )
                for rule, violation, eligible in semantic_rules(table):
                    result = records(
                        connection,
                        f"SELECT count(*) FILTER(WHERE {violation}) AS violations, "  # noqa: S608 - contract identifiers and escaped literals only
                        f"count(*) FILTER(WHERE {eligible}) AS denominator FROM {typed}",
                    )[0]
                    checks.append({"table": table, "rule": rule, "severity": "review", **result})
            verify_inputs(run, hash_content=False)
            write_json(
                run / "profile.json",
                {
                    "tables": tables,
                    "columns": columns,
                    "checks": checks,
                    "categories": categories,
                    "file_errors": errors,
                    "scope": "all_successfully_parsed_local_files",
                },
            )
        finally:
            connection.close()
