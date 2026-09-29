"""Publish a compact aggregate-only Markdown report."""

from pathlib import Path
from typing import Any

from bank_data.eda.core import phase, read_json, require


def table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    def cell(value: Any) -> str:
        return str(value if value is not None else "unknown").replace("|", "/").replace("\n", " ")

    return "\n".join(
        [
            "| " + " | ".join(columns) + " |",
            "| " + " | ".join("---" for _ in columns) + " |",
            *("| " + " | ".join(cell(row.get(col)) for col in columns) + " |" for row in rows),
        ]
    )


def report(run: Path) -> None:
    require(run, "analyze")
    with phase(run, "report"):
        manifest, inventory, profile, curate, analysis = [
            read_json(run / name)
            for name in ("manifest.json", "inventory.json", "profile.json", "curate.json", "analyze.json")
        ]
        checks = [r for r in profile["checks"] if r["violations"]]
        missing = sorted(profile["columns"], key=lambda r: (r["required"], r["missing"]), reverse=True)[:30]
        relationships = [r for r in curate["relationships"] if r["layer"] == "clean"]
        text = analysis["text"]
        sections = [
            "# Local banking dataset EDA",
            "## Reproducibility and scope",
            f"Run: `{manifest['run_id']}`. Generated from inventory dated {manifest['created_at']}. "
            f"Git revision: `{manifest['code']['git_sha']}`. Code fingerprint: `{manifest['code']['code_sha256']}`.",
            "Scope: all successfully parsed local files. Remote completeness is not verified. "
            "Inputs are synthetic organizer data; findings do not estimate real bank performance. "
            "Full local lineage and review samples remain excluded from version control.",
            "## Inventory",
            table(inventory, ["table", "files", "bytes", "schema_variants", "internal_missing_days"]),
            "## Parsing and quality",
            f"Files rejected during parsing: {len(profile['file_errors'])}. "
            "Rejected files have unknown row counts and are excluded from analytical denominators.",
            table(missing, ["table", "column", "required", "denominator", "missing", "invalid_type"]),
            table(checks, ["table", "rule", "violations", "denominator"]),
            "## Conservation of rows",
            curate["policy"],
            table(
                curate["tables"],
                ["table", "original_rows", "clean_rows", "collapsed_duplicates", "invalid_required", "conflicting_key"],
            ),
            "## Relationships",
            table(
                relationships,
                [
                    "child",
                    "column",
                    "parent",
                    "state",
                    "nonnull_fk",
                    "matched",
                    "unmatched",
                    "ambiguous_parent_rows",
                    "left_join_rows",
                ],
            ),
            table(curate["consistency"], ["child", "parent", "identity", "matched_rows", "mismatches"]),
            "## Demand and measured outcomes",
            table(
                analysis["demand_summary"],
                [
                    "layer",
                    "reason",
                    "contacts",
                    "resolution_known",
                    "resolution_rate",
                    "escalation_known",
                    "escalation_rate",
                    "mean_wait_seconds",
                ],
            ),
            table(
                analysis["outcomes"].get("surveys", []),
                ["survey_type", "responses", "valid_scores", "mean_csat", "nps"],
            ),
            table(
                analysis["outcomes"].get("currency", []),
                ["currency", "transactions", "missing_usd", "recomputable", "conversion_denominator", "converted_usd"],
            ),
            "Demand aggregates include raw and curated layers with month, country, segment, channel and reason. "
            "Unknown dimensions remain visible. Resolution, escalation and follow-up rates "
            "use known-value denominators. "
            "Duration averages exclude negative or missing values; historical flags do not measure automation safety.",
            "Open complaints are censored; observed resolution duration excludes unresolved cases. "
            "CSAT and NPS use their own valid score scales; CES has no documented scale. "
            "Currency totals remain separated. USD conversion uses direct positive rates on the event date, "
            "without forward filling or replacing source amounts.",
            "## Text and evaluation feasibility",
            table(
                [text.get("summary", {})],
                ["rows_with_customer_text", "exact_groups", "normalized_groups", "median_characters"],
            ),
            table([text.get("labels", {})], ["linked_rows", "reason_equals_category"]),
            table([text.get("contradictions", {})], ["groups", "rows"]),
            table(
                [text.get("temporal_probe", {})],
                ["cutoff", "earlier_rows", "later_rows", "later_rows_with_seen_text", "later_rows_with_seen_customer"],
            ),
            "The temporal probe uses the 80th percentile of linked interaction times. It is not a committed split. "
            "Repeated templates, shared customers and post-outcome fields must be controlled before model evaluation. "
            "Language codes describe recorded metadata, not independently verified language. "
            "Any team-generated Portuguese cases must be identified separately.",
            "## Workflow comparison",
            table(
                analysis["workflows"],
                ["workflow", "demand_status", "demand_evidence", "dependencies", "implementation_complexity"],
            ),
            analysis["recommendation"],
            "## Next decisions",
            "Review the local stratified text sample, validate label meaning and "
            "inspect high-impact relationship failures before selecting the workflow. "
            "No final weighted ranking or production benefit is inferred from these synthetic records.",
        ]
        temporary = run / "report.md.tmp"
        temporary.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
        temporary.replace(run / "report.md")
