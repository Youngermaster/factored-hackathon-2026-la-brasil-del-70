"""Aggregate demand, text diversity, evaluation viability and workflow evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bank_data.eda.core import POST_OUTCOME, connect, literal, phase, read_json, records, require, write_json


def demand(connection: Any, available: set[str]) -> list[dict[str, Any]]:
    if "call_center_interactions" not in available:
        return []
    results: list[dict[str, Any]] = []
    for layer in ("typed", "clean"):
        customer_join = (
            "LEFT JOIN clean.customers c USING (customer_id)"
            if "customers" in available
            else "LEFT JOIN (SELECT NULL::VARCHAR AS customer_id, NULL::VARCHAR AS country, "
            "NULL::VARCHAR AS segment) c USING (customer_id)"
        )
        results.extend(
            {"layer": layer, **row}
            for row in records(
                connection,
                "SELECT strftime(interaction_date, '%Y-%m') AS month, coalesce(c.country,'[unknown]') AS country, "  # noqa: S608 - contract identifiers and escaped literals only
                "coalesce(c.segment,'[unknown]') AS segment, coalesce(channel,'[missing]') AS channel, "
                "coalesce(contact_reason,'[missing]') AS reason, count(*) AS contacts, "
                "count(was_resolved) AS resolution_known, count(*) FILTER(WHERE was_resolved) AS resolved, "
                "count(was_escalated) AS escalation_known, count(*) FILTER(WHERE was_escalated) AS escalated, "
                "count(requires_followup) AS followup_known, count(*) FILTER(WHERE requires_followup) AS followup, "
                "count(*) FILTER(WHERE duration_seconds>=0) AS duration_known, "
                "sum(duration_seconds) FILTER(WHERE duration_seconds>=0) AS duration_seconds, "
                "count(*) FILTER(WHERE wait_time_seconds>=0) AS wait_known, "
                "sum(wait_time_seconds) FILTER(WHERE wait_time_seconds>=0) AS wait_seconds "
                f"FROM {layer}.call_center_interactions i {customer_join} GROUP BY 1,2,3,4,5 ORDER BY 1,2,3,4,5",
            )
        )
    return results


def text_analysis(connection: Any, run: Path, available: set[str]) -> dict[str, Any]:
    if "call_transcripts" not in available:
        return {"state": "unavailable"}
    # NFC, case and whitespace normalization only; no semantic matching or synthetic labels.
    connection.execute(
        "CREATE OR REPLACE TABLE audit.text_groups AS SELECT *, "
        "sha256(customer_text) AS exact_text_group, "
        "sha256(lower(trim(regexp_replace(nfc_normalize(customer_text), '\\s+', ' ', 'g')))) "
        "AS normalized_text_group FROM clean.call_transcripts WHERE NULLIF(trim(customer_text),'') IS NOT NULL"
    )
    summary = records(
        connection,
        "SELECT count(*) AS rows_with_customer_text, "
        "count(DISTINCT exact_text_group) AS exact_groups, "
        "count(DISTINCT normalized_text_group) AS normalized_groups, "
        "median(length(customer_text)) AS median_characters FROM audit.text_groups",
    )[0]
    concentration = records(
        connection,
        "SELECT count(*) AS repetitions FROM audit.text_groups GROUP BY "
        "normalized_text_group ORDER BY repetitions DESC LIMIT 20",
    )
    languages = records(
        connection,
        "SELECT detected_language AS language, count(*) AS rows FROM clean.call_transcripts GROUP BY 1 ORDER BY 2 DESC",
    )
    result: dict[str, Any] = {
        "state": "measured",
        "summary": summary,
        "largest_groups": concentration,
        "languages": languages,
        "post_outcome_not_intake_features": POST_OUTCOME,
    }
    if "call_center_interactions" not in available:
        return result
    connection.execute(
        "CREATE OR REPLACE VIEW audit.text_labels AS SELECT t.*, i.contact_reason, "
        "i.reason_category, i.channel, i.interaction_date FROM audit.text_groups t "
        "JOIN clean.call_center_interactions i USING (interaction_id) "
        "WHERE t.customer_id=i.customer_id"
    )
    result["labels"] = records(
        connection,
        "SELECT count(*) AS linked_rows, "
        "count(*) FILTER(WHERE contact_reason=reason_category) AS reason_equals_category "
        "FROM audit.text_labels",
    )[0]
    result["contradictions"] = records(
        connection,
        "SELECT count(*) AS groups, sum(n) AS rows FROM "
        "(SELECT normalized_text_group, count(*) AS n FROM audit.text_labels "
        "GROUP BY 1 HAVING count(DISTINCT contact_reason)>1)",
    )[0]
    cutoff_row = connection.execute("SELECT quantile_disc(interaction_date,0.8) FROM audit.text_labels").fetchone()
    cutoff = cutoff_row[0] if cutoff_row else None
    if cutoff:
        cut = literal(str(cutoff)) + "::TIMESTAMP"
        result["temporal_probe"] = {
            "cutoff": str(cutoff),
            "definition": "80th percentile of linked interaction times; "
            "a feasibility probe, not a committed train/test split",
            **records(
                connection,
                "SELECT count(*) FILTER(WHERE interaction_date <= " + cut + ") AS earlier_rows, "  # noqa: S608 - contract identifiers and escaped literals only
                "count(*) FILTER(WHERE interaction_date > " + cut + ") AS later_rows, "
                "count(*) FILTER(WHERE interaction_date > " + cut + " AND normalized_text_group IN "
                "(SELECT normalized_text_group FROM audit.text_labels WHERE interaction_date <= "
                + cut
                + ")) AS later_rows_with_seen_text, count(*) FILTER(WHERE interaction_date > "
                + cut
                + " AND customer_id IN (SELECT customer_id FROM audit.text_labels WHERE interaction_date <= "
                + cut
                + ")) AS later_rows_with_seen_customer FROM audit.text_labels",
            )[0],
        }
    country_join = (
        "LEFT JOIN clean.customers c ON t.customer_id=c.customer_id"
        if "customers" in available
        else "LEFT JOIN (SELECT NULL::VARCHAR AS customer_id, NULL::VARCHAR AS country) c "
        "ON t.customer_id=c.customer_id"
    )
    # Local-only review material. Never read by Streamlit or included in the Markdown report.
    review = records(
        connection,
        "WITH candidates AS (SELECT t._source_file AS source_file, "  # noqa: S608 - contract identifiers and escaped literals only
        "t._source_row AS source_row, t.customer_text, t.contact_reason AS reason, t.channel, "
        "coalesce(c.country,'[unknown]') AS country, strftime(t.interaction_date,'%Y-%m') AS month, "
        "t.normalized_text_group, row_number() OVER (PARTITION BY t.contact_reason,t.channel,"
        "c.country,date_trunc('month',t.interaction_date) ORDER BY sha256(t.transcript_id || '70')) AS r "
        f"FROM audit.text_labels t {country_join}) SELECT * EXCLUDE(r) FROM candidates "
        "ORDER BY r, sha256(source_file || cast(source_row AS VARCHAR) || '70') LIMIT 1200",
    )
    temporary = run / "private_review.jsonl.tmp"
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, default=str) + "\n" for row in review), encoding="utf-8"
    )
    temporary.replace(run / "private_review.jsonl")
    result["review_sample"] = {
        "rows": len(review),
        "seed": 70,
        "max_rows": 1200,
        "strata": ["reason", "channel", "country", "month"],
        "purpose": "Local manual review only; not representative or ground truth",
    }
    return result


def outcomes(connection: Any, available: set[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if "complaints" in available:
        result["complaints"] = records(
            connection,
            "SELECT strftime(creation_date,'%Y-%m') AS month, category, status, count(*) AS cases, "
            "count(origin_interaction_id) AS linked_interaction_ids, count(sla_breached) AS sla_known, "
            "count(*) FILTER(WHERE sla_breached) AS sla_breached, "
            "count(*) FILTER(WHERE resolution_date>=creation_date) AS observed_resolutions, "
            "median(date_diff('hour',creation_date,resolution_date)/24.0) "
            "FILTER(WHERE resolution_date>=creation_date) AS median_observed_resolution_days, "
            "count(*) FILTER(WHERE status IN ('Open','In Process','Escalated')) AS open_cases "
            "FROM clean.complaints GROUP BY 1,2,3 ORDER BY 1,2,3",
        )
        result["censoring_note"] = (
            "Open cases are censored. Resolution duration describes observed resolutions only. "
            "Extraction time is unavailable; process_date is not an observation cutoff."
        )
    if "satisfaction_surveys" in available:
        result["surveys"] = records(
            connection,
            "SELECT survey_type, count(*) AS responses, count(main_score) AS score_known, "
            "count(*) FILTER(WHERE survey_type='CSAT' AND main_score BETWEEN 1 AND 5 OR "
            "survey_type='NPS' AND main_score BETWEEN 0 AND 10) AS valid_scores, "
            "avg(main_score) FILTER(WHERE survey_type='CSAT' AND main_score BETWEEN 1 AND 5) AS mean_csat, "
            "100.0 * (count(*) FILTER(WHERE survey_type='NPS' AND main_score BETWEEN 9 AND 10) - "
            "count(*) FILTER(WHERE survey_type='NPS' AND main_score BETWEEN 0 AND 6)) / "
            "nullif(count(*) FILTER(WHERE survey_type='NPS' AND main_score BETWEEN 0 AND 10),0) AS nps, "
            "count(DISTINCT interaction_id) AS distinct_linked_interactions FROM clean.satisfaction_surveys "
            "GROUP BY 1 ORDER BY 1",
        )
        result["ces_note"] = "CES scale is undocumented: report distribution only, without a composite score."
    if {"transactions", "daily_exchange_rates"} <= available:
        result["currency"] = records(
            connection,
            "SELECT t.currency, count(*) AS transactions, count(*) FILTER(WHERE t.amount_usd IS NULL) AS missing_usd, "
            "count(*) FILTER(WHERE t.amount_usd IS NULL AND (t.currency='USD' OR f.exchange_rate>0)) AS recomputable, "
            "sum(t.amount) AS amount_in_source_currency, sum(CASE WHEN t.currency='USD' THEN t.amount "
            "WHEN f.exchange_rate>0 THEN round(t.amount*f.exchange_rate,2) ELSE NULL END) AS converted_usd, "
            "count(*) FILTER(WHERE t.currency='USD' OR f.exchange_rate>0) AS conversion_denominator "
            "FROM clean.transactions t LEFT JOIN clean.daily_exchange_rates f ON "
            "cast(t.transaction_date AS DATE)=f.date AND t.currency=f.source_currency AND f.target_currency='USD' "
            "GROUP BY 1 ORDER BY 1",
        )
        result["fx_policy"] = (
            "Exact event date and direct source-to-USD positive rate only; no forward fill or inversion. "
            "USD uses identity conversion. Converted values do not replace source amounts."
        )
    return result


def workflows(
    available: set[str], profile_data: dict[str, Any], curated: dict[str, Any], text: dict[str, Any]
) -> list[dict[str, Any]]:
    definitions = [
        (
            "accounts_payments",
            ["customers", "products", "transactions"],
            "Transactional contacts are a broad proxy; payment inquiries are not separately labeled.",
            "Verify ownership and transaction status; synthetic authenticated read tools required.",
            "medium",
        ),
        (
            "card_support",
            ["customers", "products", "transactions"],
            "Product and transactional contacts do not isolate card-service requests.",
            "Requires a card subset, confirmation rules and verified mock block/unblock actions.",
            "medium",
        ),
        (
            "disputes",
            ["customers", "products", "transactions", "complaints"],
            "Complaint categories support a proxy; transaction disputes lack a verified transaction link.",
            "Requires synthetic dispute policy, explicit transaction selection and documented handoff.",
            "high",
        ),
        (
            "product_information",
            ["products", "call_center_interactions"],
            "Product contacts are a broad proxy; individual customer holdings are not a public product catalog.",
            "Requires approved or clearly synthetic product terms; no inferred credit eligibility.",
            "medium",
        ),
    ]
    clean_counts = {row["table"]: row["clean_rows"] for row in curated["tables"]}
    parse_errors = {row["table"] for row in profile_data["file_errors"]}
    result = []
    for name, tables, demand_note, dependency, complexity in definitions:
        result.append(
            {
                "workflow": name,
                "required_tables": tables,
                "missing_tables": sorted(set(tables) - available),
                "tables_with_parse_errors": sorted(set(tables) & parse_errors),
                "clean_rows_by_table": {t: clean_counts.get(t, 0) for t in tables},
                "demand_status": "unknown_at_workflow_granularity",
                "demand_evidence": demand_note,
                "dependencies": dependency,
                "implementation_complexity": complexity,
                "evaluation_limit": "Repeated templates require grouped evaluation and manual label validation.",
                "text_diversity": text.get("summary", {}),
                "relationship_evidence": [
                    r for r in curated["relationships"] if r["layer"] == "clean" and r["child"] in tables
                ],
                "automated_rank": None,
            }
        )
    return result


def demand_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Summable counts first; rates are recomputed, never averaged across groups."""
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    metrics = (
        "contacts",
        "resolved",
        "resolution_known",
        "escalated",
        "escalation_known",
        "followup",
        "followup_known",
        "duration_seconds",
        "duration_known",
        "wait_seconds",
        "wait_known",
    )
    for row in rows:
        key = row["layer"], row["reason"]
        group = groups.setdefault(key, {"layer": key[0], "reason": key[1], **dict.fromkeys(metrics, 0)})
        for metric in metrics:
            group[metric] += row[metric] or 0
    for group in groups.values():
        for label, num, den in [
            ("resolution_rate", "resolved", "resolution_known"),
            ("escalation_rate", "escalated", "escalation_known"),
            ("followup_rate", "followup", "followup_known"),
            ("mean_duration_seconds", "duration_seconds", "duration_known"),
            ("mean_wait_seconds", "wait_seconds", "wait_known"),
        ]:
            group[label] = round(group[num] / group[den], 4) if group[den] else None
    return [groups[key] for key in sorted(groups)]


def recommendation(matrix: list[dict[str, Any]], curated: dict[str, Any]) -> str:
    usable = [
        w["workflow"]
        for w in matrix
        if not w["missing_tables"] and not w["tables_with_parse_errors"] and all(w["clean_rows_by_table"].values())
    ]
    inconsistent = sum(row["mismatches"] for row in curated["consistency"])
    return (
        f"Workflows with all required tables containing usable rows: {', '.join(usable) or 'none'}. "
        f"Cross-record identity mismatches observed: {inconsistent}. "
        "Compare account/payment inquiry feasibility against dispute intake using the relationship coverage above. "
        "Account/payment inquiries avoid the unverified complaint-to-transaction link, but still require "
        "ownership checks. Defer a final workflow choice until contact-label review and identity mismatch "
        "resolution. Broad category counts and synthetic outcome flags alone do not justify a winner."
    )


def analyze(run: Path) -> None:
    require(run, "curate")
    with phase(run, "analyze"):
        connection = connect(run)
        try:
            profile_data = read_json(run / "profile.json")
            curated = read_json(run / "curate.json")
            available = {row["table"] for row in profile_data["tables"]}
            text = text_analysis(connection, run, available)
            demand_rows = demand(connection, available)
            matrix = workflows(available, profile_data, curated, text)
            result = {
                "demand": demand_rows,
                "demand_summary": demand_summary(demand_rows),
                "outcomes": outcomes(connection, available),
                "text": text,
                "workflows": matrix,
                "recommendation": recommendation(matrix, curated),
                "provenance": "Organizer-supplied synthetic data. Historical resolution flags are not evidence "
                "of safe automated resolution or measured production impact.",
            }
            write_json(run / "analyze.json", result)
        finally:
            connection.close()
