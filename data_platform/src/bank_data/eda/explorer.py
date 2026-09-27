"""Read-only helpers for the interactive EDA laboratory."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

import duckdb

from bank_data.eda.core import CATEGORIES, CONTRACTS, qi, read_json

LAYERS = {"typed", "clean"}
SAMPLE_LIMITS = {25, 50, 100}
SAMPLE_SEED = 70
EXPECTED_ROWS = {
    "branches": 350,
    "call_center_interactions": 800_000,
    "call_transcripts": 200_000,
    "campaign_sends": 2_000_000,
    "complaints": 80_000,
    "customers": 150_000,
    "daily_exchange_rates": 3_000,
    "digital_events": 10_000_000,
    "marketing_campaigns": 200,
    "products": 400_000,
    "satisfaction_surveys": 250_000,
    "service_agents": 1_200,
    "transactions": 5_000_000,
}

# Samples fail closed: only entity references, known low-cardinality categories,
# month-bucketed dates and a few technical flags are allowed out of the warehouse.
SAFE_SAMPLE_FLAGS = {"has_atms", "has_linked_app", "has_recording", "has_transcript", "has_teller_windows"}
SAFE_SAMPLE_DATES = {
    "assignment_date",
    "branch_opening_date",
    "click_date",
    "creation_date",
    "event_date",
    "first_response_date",
    "hire_date",
    "interaction_date",
    "last_updated",
    "open_date",
    "opening_date",
    "process_date",
    "registration_date",
    "send_date",
    "survey_date",
    "transaction_date",
    "transcription_date",
}
SENSITIVE_OUTCOME_COLUMNS = {
    "compensation_granted",
    "had_conversion",
    "is_fraud",
    "requires_followup",
    "resolution_satisfaction",
    "sla_breached",
    "was_clicked",
    "was_delivered",
    "was_escalated",
    "was_opened",
    "was_resolved",
}
SAFE_SAMPLE_CATEGORIES = CATEGORIES - SENSITIVE_OUTCOME_COLUMNS


def _validated_relation(table: str, layer: str) -> str:
    if table not in CONTRACTS:
        raise ValueError("Unknown table")
    if layer not in LAYERS:
        raise ValueError("Unknown layer")
    return f"{qi(layer)}.{qi(table)}"


def safe_columns(table: str) -> list[dict[str, Any]]:
    """Return only explicitly approved fields for a sanitized sample."""
    if table not in CONTRACTS:
        raise ValueError("Unknown table")
    return [
        column
        for column in CONTRACTS[table]["columns"]
        if column["name"].endswith("_id")
        or column["name"] in SAFE_SAMPLE_CATEGORIES
        or column["name"] in SAFE_SAMPLE_FLAGS
        or column["name"] in SAFE_SAMPLE_DATES
    ]


def sample_rows(run: Path, table: str, layer: str, limit: int) -> list[dict[str, Any]]:
    """Read a deterministic, bounded sample without exposing identifiers or free text."""
    relation = _validated_relation(table, layer)
    if limit not in SAMPLE_LIMITS:
        raise ValueError("Unsupported sample size")
    warehouse = run / "warehouse.duckdb"
    if not warehouse.exists():
        return []
    expressions: list[str] = []
    aliases: list[str] = []
    for column in safe_columns(table):
        name = column["name"]
        if name.endswith("_id"):
            alias = f"{name}_ref"
            expressions.append(
                f"CASE WHEN {qi(name)} IS NULL THEN NULL "
                f"ELSE substr(sha256(CAST({qi(name)} AS VARCHAR) || ':eda-{SAMPLE_SEED}'), 1, 12) END AS {qi(alias)}"
            )
        elif name in SAFE_SAMPLE_DATES:
            alias = f"{name}_month"
            expressions.append(f"date_trunc('month', {qi(name)}) AS {qi(alias)}")
        else:
            alias = name
            expressions.append(qi(name))
        aliases.append(alias)
    query = (
        f"SELECT {', '.join(expressions)} FROM {relation} "  # noqa: S608
        f"USING SAMPLE reservoir({limit} ROWS) REPEATABLE({SAMPLE_SEED})"
    )
    with duckdb.connect(str(warehouse), read_only=True) as connection:
        values = connection.execute(query).fetchall()
    return [dict(zip(aliases, row, strict=True)) for row in values]


def sample_csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def relationship_status(row: dict[str, Any], mismatches: int = 0) -> str:
    """Classify measured joins using coverage and semantic consistency."""
    if row.get("state") != "measured" or not row.get("nonnull_fk"):
        return "gray"
    if mismatches:
        return "red"
    coverage = row.get("matched", 0) / row["nonnull_fk"]
    if coverage == 1:
        return "green"
    if coverage >= 0.95:
        return "yellow"
    return "red"


def relationship_rows(run: Path, layer: str = "clean") -> list[dict[str, Any]]:
    data = read_json(run / "curate.json")
    mismatch_by_pair = {(row["child"], row["parent"]): row["mismatches"] for row in data.get("consistency", [])}
    result = []
    for row in data.get("relationships", []):
        if row["layer"] != layer:
            continue
        item = dict(row)
        item["mismatches"] = mismatch_by_pair.get((row["child"], row["parent"]), 0)
        item["coverage_pct"] = round(100 * row["matched"] / row["nonnull_fk"], 2) if row["nonnull_fk"] else None
        item["fanout"] = round(row["left_join_rows"] / row["child_rows"], 4) if row["child_rows"] else None
        item["status"] = relationship_status(item, item["mismatches"])
        result.append(item)
    return result


def relationship_alerts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    alerts = []
    for row in rows:
        key = (row["child"], row["column"], row["parent"])
        if (
            key
            in {
                ("customers", "registration_branch_id", "branches"),
                ("service_agents", "assigned_branch_id", "branches"),
            }
            and row["status"] == "red"
        ):
            alerts.append({"relation": " -> ".join((row["child"], row["parent"])), "finding": "low_coverage"})
        if key == ("complaints", "origin_interaction_id", "call_center_interactions") and not row["nonnull_fk"]:
            alerts.append({"relation": "complaints -> call_center_interactions", "finding": "no_origin_ids"})
        if key == ("complaints", "affected_product_id", "products") and row["mismatches"]:
            alerts.append(
                {
                    "relation": "complaints -> products",
                    "finding": "different_customer_owner",
                    "rows": row["mismatches"],
                }
            )
    return alerts


def graph_dot(rows: list[dict[str, Any]], table_counts: dict[str, int]) -> str:
    colors = {"green": "#2e7d32", "yellow": "#f9a825", "red": "#c62828", "gray": "#78909c"}
    lines = ["digraph relations {", 'rankdir="LR";', 'node [shape="box", style="rounded,filled", fillcolor="#f5f7f5"];']
    tables = sorted({str(row["child"]) for row in rows} | {str(row["parent"]) for row in rows})
    for table in tables:
        lines.append(f'{qi(table)} [label="{table}\\n{table_counts.get(table, 0):,} rows"];')
    for row in rows:
        required = next(
            column["required"] for column in CONTRACTS[row["child"]]["columns"] if column["name"] == row["column"]
        )
        style = "solid" if required else "dashed"
        label = f"{row['column']} ({row['coverage_pct'] if row['coverage_pct'] is not None else 'N/A'}%)"
        lines.append(
            f"{qi(row['child'])} -> {qi(row['parent'])} "
            f'[label="{label}", color="{colors[row["status"]]}", fontcolor="{colors[row["status"]]}", style="{style}"];'
        )
    lines.append("}")
    return "\n".join(lines)


def workflow_assessments(run: Path) -> list[dict[str, Any]]:
    """Build transparent traffic lights; each status has inspectable evidence."""
    profile = read_json(run / "profile.json")
    analysis = read_json(run / "analyze.json")
    relationships = relationship_rows(run)
    table_rows = {row["table"]: row["rows"] for row in profile.get("tables", [])}
    demand = {row["reason"]: row["contacts"] for row in analysis.get("demand_summary", []) if row["layer"] == "clean"}
    specs = [
        ("accounts_payments", ["customers", "products", "transactions"], "Transaccional", "green", "green"),
        ("card_support", ["customers", "products", "transactions"], "Producto", "green", "yellow"),
        (
            "technical_support",
            ["customers", "digital_events", "call_center_interactions"],
            "Técnico",
            "yellow",
            "yellow",
        ),
        (
            "product_information",
            ["customers", "products", "call_center_interactions"],
            "Producto",
            "green",
            "red",
        ),
        ("disputes", ["complaints", "products", "transactions"], "Queja", "red", "red"),
    ]
    result = []
    for workflow, tables, reason, join_default, safety in specs:
        missing = [table for table in tables if not table_rows.get(table)]
        join_status = join_default
        critical_red = [
            row
            for row in relationships
            if row["child"] in tables and row["parent"] in tables and row["status"] == "red"
        ]
        if missing or critical_red:
            join_status = "red"
        evaluation = "red" if workflow == "disputes" or missing else "yellow"
        dimensions = [
            {
                "dimension": "data_availability",
                "status": "red" if missing else "green",
                "evidence": f"rows={{{', '.join(f'{x}: {table_rows.get(x, 0)}' for x in tables)}}}; missing={missing}",
            },
            {
                "dimension": "join_integrity",
                "status": join_status,
                "evidence": f"critical_red_relations={len(critical_red)}"
                if join_status == "red"
                else "required links measured; see relationship map",
            },
            {
                "dimension": "demand_evidence",
                "status": "red" if not demand.get(reason) else "yellow",
                "evidence": f"{reason} contacts={demand.get(reason, 0)}; category is a broad proxy",
            },
            {
                "dimension": "evaluation_readiness",
                "status": evaluation,
                "evidence": "requires grouped held-out labels and human validation"
                if evaluation == "yellow"
                else "broken complaint links prevent reliable outcome labels",
            },
            {
                "dimension": "policy_safety",
                "status": safety,
                "evidence": "read-only authenticated answers are feasible"
                if safety == "green"
                else "needs escalation, policy controls, or action authorization",
            },
        ]
        result.append({"workflow": workflow, "project_choice": workflow == "disputes", "dimensions": dimensions})
    return result
