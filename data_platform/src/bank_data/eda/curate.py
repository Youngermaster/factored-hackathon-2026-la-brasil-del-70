"""Conservative deduplication, row-level lineage and join eligibility."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bank_data.eda.core import FK, connect, fields, keys, literal, phase, qi, read_json, records, require, write_json
from bank_data.eda.profile import semantic_rules


def curate(run: Path) -> None:
    require(run, "profile")
    with phase(run, "curate"):
        connection = connect(run)
        try:
            connection.execute("DROP SCHEMA IF EXISTS clean CASCADE")
            connection.execute("DROP SCHEMA IF EXISTS audit CASCADE")
            connection.execute("CREATE SCHEMA clean")
            connection.execute("CREATE SCHEMA audit")
            summaries: list[dict[str, Any]] = []
            available = [row["table"] for row in read_json(run / "profile.json")["tables"]]
            parquet = run / "curated"
            parquet.mkdir(exist_ok=True)
            for table in available:
                name = qi(table)
                key = ", ".join(qi(k) for k in keys(table))
                # All conflicting versions stay in raw. No arbitrary last-write-wins policy.
                connection.execute(
                    f"CREATE TABLE audit.{qi(table + '_conflicts')} AS "  # noqa: S608 - contract identifiers and escaped literals only
                    f"SELECT {key} FROM raw.{name} GROUP BY {key} HAVING count(DISTINCT _row_hash)>1"
                )
                required = [
                    f"{qi(c['name'])} IS NULL"
                    + (f" OR trim({qi(c['name'])})=''" if str(c["type"]).startswith(("VARCHAR", "TEXT")) else "")
                    for c in fields(table)
                    if c["required"]
                ]
                invalid = " OR ".join(f"({expression})" for expression in required) or "false"
                rules = semantic_rules(table)
                issue_items = ", ".join(
                    f"CASE WHEN {predicate} THEN {literal(rule)} END" for rule, predicate, _ in rules
                )
                issue_list = f"list_filter([{issue_items}], x -> x IS NOT NULL)" if rules else "[]::VARCHAR[]"
                match = " AND ".join(f"t.{qi(k)} IS NOT DISTINCT FROM c.{qi(k)}" for k in keys(table))
                connection.execute(
                    f"CREATE TABLE audit.{qi(table + '_rows')} AS SELECT _source_file, _source_row, "  # noqa: S608 - contract identifiers and escaped literals only
                    f"_row_hash, {issue_list} AS semantic_issues, CASE WHEN {invalid} THEN 'invalid_required' "
                    f"WHEN EXISTS (SELECT 1 FROM audit.{qi(table + '_conflicts')} c WHERE {match}) "
                    "THEN 'conflicting_key' ELSE 'eligible' END AS disposition "
                    f"FROM typed.{name} t"
                )
                connection.execute(
                    f"CREATE TABLE clean.{name} AS SELECT t.* FROM typed.{name} t "  # noqa: S608 - contract identifiers and escaped literals only
                    f"JOIN audit.{qi(table + '_rows')} a USING (_source_file, _source_row) "
                    "WHERE a.disposition='eligible' QUALIFY row_number() OVER "
                    "(PARTITION BY t._row_hash ORDER BY t._source_file, t._source_row)=1"
                )
                result = records(
                    connection,
                    f"SELECT count(*) AS original_rows, "  # noqa: S608 - contract identifiers and escaped literals only
                    "count(*) FILTER(WHERE disposition='invalid_required') AS invalid_required, "
                    "count(*) FILTER(WHERE disposition='conflicting_key') AS conflicting_key, "
                    "count(*) FILTER(WHERE disposition='eligible') AS eligible_before_dedup "
                    f"FROM audit.{qi(table + '_rows')}",
                )[0]
                result["clean_rows"] = connection.execute(f"SELECT count(*) FROM clean.{name}").fetchone()[0]  # noqa: S608 - contract identifiers and escaped literals only
                result["collapsed_duplicates"] = result["eligible_before_dedup"] - result["clean_rows"]
                result["table"] = table
                if "last_updated" in {c["name"] for c in fields(table)}:
                    result["potential_versioned_keys"] = connection.execute(
                        f"SELECT count(*) FROM (SELECT {key} FROM typed.{name} GROUP BY {key} "  # noqa: S608 - contract identifiers and escaped literals only
                        "HAVING count(DISTINCT last_updated)>1)"
                    ).fetchone()[0]
                summaries.append(result)
                target = parquet / (table + ".parquet")
                temporary = target.with_suffix(".parquet.tmp")
                connection.execute(f"COPY clean.{name} TO {literal(str(temporary))} (FORMAT PARQUET, COMPRESSION ZSTD)")
                temporary.replace(target)
            relationships = []
            for child, references in FK.items():
                if child not in available:
                    continue
                for field, (parent, parent_key) in references.items():
                    for layer in ("typed", "clean"):
                        relation = f"{layer}.{qi(child)}"
                        if parent not in available:
                            relationships.append(
                                {
                                    "child": child,
                                    "column": field,
                                    "parent": parent,
                                    "layer": layer,
                                    "state": "parent_unavailable",
                                }
                            )
                            continue
                        # Parent key frequencies expose fanout instead of accidentally multiplying rows.
                        query = (
                            f"WITH parents AS (SELECT {qi(parent_key)} AS pk, count(*) AS n FROM {layer}.{qi(parent)} "  # noqa: S608 - contract identifiers and escaped literals only
                            f"GROUP BY 1) SELECT count(*) AS child_rows, count(c.{qi(field)}) AS nonnull_fk, "
                            f"count(*) FILTER(WHERE c.{qi(field)} IS NOT NULL AND p.pk IS NULL) AS unmatched, "
                            "count(*) FILTER(WHERE p.pk IS NOT NULL) AS matched, "
                            "count(*) FILTER(WHERE p.n>1) AS ambiguous_parent_rows, "
                            "coalesce(sum(p.n),0) AS inner_join_rows, "
                            "coalesce(sum(greatest(coalesce(p.n,0),1)),0) AS left_join_rows "
                            f"FROM {relation} c LEFT JOIN parents p ON c.{qi(field)}=p.pk"
                        )
                        relationships.append(
                            {
                                "child": child,
                                "column": field,
                                "parent": parent,
                                "layer": layer,
                                "state": "measured",
                                **records(connection, query)[0],
                            }
                        )
            consistency = []
            specs = [
                ("transactions", "product_id", "products", "product_id", "customer_id"),
                ("complaints", "affected_product_id", "products", "product_id", "customer_id"),
                ("call_transcripts", "interaction_id", "call_center_interactions", "interaction_id", "customer_id"),
                ("call_transcripts", "interaction_id", "call_center_interactions", "interaction_id", "agent_id"),
                ("satisfaction_surveys", "interaction_id", "call_center_interactions", "interaction_id", "customer_id"),
            ]
            for child, fk, parent, pk, identity in specs:
                if child not in available or parent not in available:
                    continue
                result = records(
                    connection,
                    f"SELECT count(*) AS matched_rows, count(*) FILTER(WHERE "  # noqa: S608 - contract identifiers and escaped literals only
                    f"c.{qi(identity)} IS DISTINCT FROM p.{qi(identity)}) AS mismatches "
                    f"FROM clean.{qi(child)} c JOIN clean.{qi(parent)} p ON c.{qi(fk)}=p.{qi(pk)}",
                )[0]
                consistency.append({"child": child, "parent": parent, "identity": identity, **result})
            write_json(
                run / "curate.json",
                {
                    "tables": summaries,
                    "relationships": relationships,
                    "consistency": consistency,
                    "policy": "Exact row collapse; required-field failures and conflicting keys excluded. "
                    "Optional invalid casts become null and remain counted in the profile. "
                    "Orphans and semantic anomalies stay flagged, not silently dropped.",
                },
            )
        finally:
            connection.close()
