"""Synthetic fixtures: no organizer rows or external services are used."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import duckdb
import pytest
from typer.testing import CliRunner

from bank_data.cli import app
from bank_data.eda.analyze import analyze
from bank_data.eda.core import CONTRACTS, connect, digest, phase, qi, read_json, require, writer_is_active
from bank_data.eda.curate import curate
from bank_data.eda.explorer import (
    graph_dot,
    relationship_alerts,
    relationship_rows,
    safe_columns,
    sample_rows,
    workflow_assessments,
)
from bank_data.eda.inventory import inventory, verify_inputs
from bank_data.eda.profile import profile
from bank_data.eda.report import report
from bank_data.eda.ui import display_rows


def row(table: str, **overrides: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for col in CONTRACTS[table]["columns"]:
        kind, name = col["type"], col["name"]
        if kind == "DATE":
            result[name] = "2024-01-01"
        elif kind == "TIMESTAMP":
            result[name] = "2024-01-01 12:00:00"
        elif kind == "TIME":
            result[name] = "09:00:00"
        elif kind == "BOOLEAN":
            result[name] = "True"
        elif kind.startswith(("DECIMAL", "INTEGER")):
            result[name] = "1"
        else:
            result[name] = name if col["required"] else ""
    result.update(overrides)
    return result


def csv_file(source: Path, table: str, rows: list[dict[str, Any]], filename: str | None = None) -> Path:
    path = source / (filename or f"{table}.csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=[c["name"] for c in CONTRACTS[table]["columns"]])
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.fixture
def source(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    for table in CONTRACTS:
        csv_file(root, table, [row(table)])
    csv_file(root, "customers", [row("customers", country="Colombia", segment="Basic", credit_score=650)])
    csv_file(root, "products", [row("products", currency="COP", product_status="Active")])
    csv_file(
        root,
        "daily_exchange_rates",
        [row("daily_exchange_rates", source_currency="COP", target_currency="USD", exchange_rate="0.000250")],
    )
    csv_file(root, "transactions", [row("transactions", currency="COP", amount="4000.00", amount_usd="")])
    calls = [
        row(
            "call_center_interactions",
            interaction_id=f"i{i}",
            contact_reason="Transaccional",
            reason_category="Transaccional",
            channel="Phone",
            interaction_date=f"2024-01-0{i} 12:00:00",
            duration_seconds="20",
            wait_time_seconds="5",
        )
        for i in range(1, 4)
    ]
    csv_file(root, "call_center_interactions", calls)
    texts = [
        row(
            "call_transcripts",
            transcript_id=f"t{i}",
            interaction_id=f"i{i}",
            customer_text="Consulta sintética\nmultilínea",
            full_text="Consulta sintética\nmultilínea",
            detected_language="es",
            duration_seconds="20",
            mentioned_entities="{}",
        )
        for i in range(1, 4)
    ]
    csv_file(root, "call_transcripts", texts)
    csv_file(
        root,
        "complaints",
        [
            row(
                "complaints",
                status="Open",
                origin_interaction_id="",
                affected_product_id="product_id",
                customer_id="different_customer",
                category="Fees",
            )
        ],
    )
    csv_file(
        root,
        "satisfaction_surveys",
        [
            row("satisfaction_surveys", interaction_id="i1", survey_type="CSAT", main_score=4),
            row("satisfaction_surveys", survey_id="s2", interaction_id="i2", survey_type="NPS", main_score=10),
            row("satisfaction_surveys", survey_id="s3", interaction_id="i3", survey_type="CES", main_score=7),
        ],
    )
    return root


@pytest.fixture
def complete_run(source: Path, tmp_path: Path) -> Path:
    run = inventory(source, tmp_path / "output")
    profile(run)
    curate(run)
    analyze(run)
    report(run)
    return run


def test_full_run_preserves_inputs_and_measures_text_currency_and_denominators(
    source: Path, complete_run: Path
) -> None:
    before = {p: digest(p) for p in source.rglob("*.csv")}
    verify_inputs(complete_run)  # Compare current source bytes against the pre-ingestion manifest.
    summary = read_json(complete_run / "analyze.json")
    assert summary["text"]["summary"]["rows_with_customer_text"] == 3
    assert summary["text"]["summary"]["normalized_groups"] == 1
    assert summary["text"]["labels"]["linked_rows"] == 3
    assert summary["text"]["temporal_probe"]["later_rows_with_seen_text"] == 0  # 3-row quantile lands on last date.
    fx = summary["outcomes"]["currency"][0]
    assert fx["recomputable"] == 1
    assert float(fx["converted_usd"]) == 1
    assert summary["outcomes"]["surveys"][1]["mean_csat"] == 4
    assert all(v["state"] == "complete" for v in read_json(complete_run / "status.json").values())
    assert {p: digest(p) for p in source.rglob("*.csv")} == before
    assert "Consulta sintética" not in (complete_run / "report.md").read_text()
    assert len(list((complete_run / "curated").glob("*.parquet"))) == 13
    report_text = (complete_run / "report.md").read_text()
    report(complete_run)
    assert (complete_run / "report.md").read_text() == report_text


def test_dedup_conflicts_required_failures_and_orphans_are_separate(source: Path, tmp_path: Path) -> None:
    original = row("transactions", transaction_id="exact", product_id="missing", currency="COP")
    csv_file(
        source,
        "transactions",
        [
            original,
            row("transactions", transaction_id="conflict", amount="1"),
            row("transactions", transaction_id="conflict", amount="2"),
            row("transactions", transaction_id="invalid", amount="not-money"),
        ],
    )
    csv_file(source, "transactions", [original], "transactions/year=2024/month=01/day=02/extra.csv")
    run = inventory(source, tmp_path / "output")
    profile(run)
    curate(run)
    stats = next(r for r in read_json(run / "curate.json")["tables"] if r["table"] == "transactions")
    assert stats["original_rows"] == 5
    assert stats["clean_rows"] == 1
    assert stats["collapsed_duplicates"] == 1
    assert stats["conflicting_key"] == 2
    assert stats["invalid_required"] == 1
    connection = connect(run)
    assert connection.execute("SELECT count(*) FROM audit.transactions_rows").fetchone()[0] == 5
    assert connection.execute("SELECT amount FROM clean.transactions").fetchone()[0] == 1
    connection.close()
    link = next(
        r
        for r in read_json(run / "curate.json")["relationships"]
        if r["child"] == "transactions" and r["column"] == "product_id" and r["layer"] == "clean"
    )
    assert link["unmatched"] == 1
    assert link["left_join_rows"] == 1


def test_manifest_excludes_outputs_reuses_identity_and_detects_mutation(source: Path) -> None:
    output = source / "eda"
    run = inventory(source, output)
    assert inventory(source, output) == run
    (output / "customers.csv").write_text("ignore me")
    assert inventory(source, output) == run
    with (source / "customers.csv").open("a") as stream:
        stream.write("\n")
    with pytest.raises(RuntimeError, match="changed"):
        verify_inputs(run)
    assert inventory(source, output) != run


def test_failed_phase_is_not_complete_and_raw_errors_are_not_written(source: Path, tmp_path: Path) -> None:
    run = inventory(source, tmp_path / "out")
    with pytest.raises(ValueError, match="PRIVATE"), phase(run, "profile"):
        raise ValueError("PRIVATE record content")
    assert "PRIVATE" not in (run / "status.json").read_text()
    assert read_json(run / "status.json")["profile"]["state"] == "failed"
    with pytest.raises(RuntimeError, match="Complete"):
        require(run, "profile")
    with phase(run, "profile"), pytest.raises(RuntimeError, match="locked"), phase(run, "profile"):
        pytest.fail("A second writer must not enter")


def test_dead_writer_lock_is_released_when_reusing_inventory(
    source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = inventory(source, tmp_path / "out")
    lock = run / ".writer.lock"
    lock.write_text('{"pid": 999999}')

    def missing_process(_: int, __: int) -> None:
        raise ProcessLookupError

    monkeypatch.setattr("bank_data.eda.core.os.kill", missing_process)
    assert not writer_is_active(lock)
    assert inventory(source, tmp_path / "out") == run
    assert not lock.exists()


def test_legacy_writer_lock_stays_protected(tmp_path: Path) -> None:
    lock = tmp_path / ".writer.lock"
    lock.write_text("2026-09-27T19:15:34+00:00")
    assert writer_is_active(lock)


def test_partial_dataset_reports_absent_parents_and_never_assumes_complete(tmp_path: Path) -> None:
    source = tmp_path / "source"
    csv_file(source, "transactions", [row("transactions")])
    run = inventory(source, tmp_path / "out")
    profile(run)
    curate(run)
    analyze(run)
    report(run)
    result = read_json(run / "curate.json")
    assert all(r["state"] == "parent_unavailable" for r in result["relationships"])
    assert read_json(run / "analyze.json")["text"]["state"] == "unavailable"
    assert read_json(run / "manifest.json")["remote_completeness"] == "not_verified"


def test_malformed_file_is_accounted_for_and_does_not_disappear(tmp_path: Path) -> None:
    source = tmp_path / "source"
    path = csv_file(source, "customers", [row("customers")])
    with path.open("a") as stream:
        stream.write('"unterminated field\n')
    run = inventory(source, tmp_path / "out")
    profile(run)
    result = read_json(run / "profile.json")
    assert len(result["file_errors"]) == 1
    assert result["tables"][0]["rows"] == 0


def test_dynamic_identifiers_are_rejected_and_paths_with_quotes_are_safe(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="identifier"):
        qi("customers; DROP TABLE anything")
    source = tmp_path / "quote's"
    csv_file(source, "branches", [row("branches")])
    run = inventory(source, tmp_path / "out")
    profile(run)
    assert read_json(run / "profile.json")["tables"][0]["rows"] == 1


def test_cli_runs_and_reuses_completed_phases(source: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    args = ["eda", "run", "--source", str(source), "--output", str(tmp_path / "out")]
    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.output
    second = runner.invoke(app, args)
    assert second.exit_code == 0
    assert "Reusing completed phase: report" in second.output
    bad = runner.invoke(app, ["eda", "profile", str(tmp_path)])
    assert bad.exit_code == 1
    assert "raw errors are suppressed" in bad.output


def test_lineage_preserves_multiline_csv_record_ordinals(complete_run: Path) -> None:
    with duckdb.connect(str(complete_run / "warehouse.duckdb"), read_only=True) as connection:
        assert connection.execute("SELECT _source_row FROM raw.call_transcripts ORDER BY _source_row").fetchall() == [
            (1,),
            (2,),
            (3,),
        ]


def test_viewer_normalizes_only_heterogeneous_aggregate_columns() -> None:
    rows = [
        {"table": "customers", "minimum": 1, "missing": 0},
        {"table": "branches", "minimum": "2024-01-01", "missing": 1},
    ]
    assert display_rows(rows) == [
        {"table": "customers", "minimum": "1", "missing": 0},
        {"table": "branches", "minimum": "2024-01-01", "missing": 1},
    ]


def test_viewer_formats_absent_and_compound_values_for_tables() -> None:
    assert display_rows([{"rank": None, "evidence": {"tables": ["customers", "products"]}}]) == [
        {"rank": "Sin dato", "evidence": '{"tables": ["customers", "products"]}'}
    ]


def test_viewer_rectangularizes_sparse_aggregate_rows() -> None:
    assert display_rows([{"column": "text"}, {"column": "amount", "minimum": 1}]) == [
        {"column": "text", "minimum": "Sin dato"},
        {"column": "amount", "minimum": "1"},
    ]


def test_sanitized_samples_are_deterministic_bounded_and_read_only(complete_run: Path) -> None:
    warehouse = complete_run / "warehouse.duckdb"
    before = (warehouse.stat().st_mtime_ns, digest(warehouse))
    first = sample_rows(complete_run, "customers", "clean", 25)
    second = sample_rows(complete_run, "customers", "clean", 25)
    assert first == second
    assert len(first) <= 25
    assert first
    assert "customer_id_ref" in first[0]
    assert len(first[0]["customer_id_ref"]) == 12
    assert (
        not {
            "document_number",
            "first_name",
            "last_name",
            "email",
            "date_of_birth",
            "city",
            "gender",
            "credit_score",
            "estimated_monthly_income",
        }
        & first[0].keys()
    )
    assert (warehouse.stat().st_mtime_ns, digest(warehouse)) == before
    with pytest.raises(ValueError, match="Unknown table"):
        sample_rows(complete_run, "customers; DROP TABLE customers", "clean", 25)
    with pytest.raises(ValueError, match="Unknown layer"):
        sample_rows(complete_run, "customers", "private", 25)
    with pytest.raises(ValueError, match="sample size"):
        sample_rows(complete_run, "customers", "clean", 1000)


def test_sanitized_samples_exclude_transcript_text(complete_run: Path) -> None:
    rows = sample_rows(complete_run, "call_transcripts", "typed", 25)
    assert rows
    assert not {"full_text", "customer_text", "agent_text", "mentioned_entities"} & rows[0].keys()
    assert "Consulta sintética" not in str(rows)


def test_sample_allowlist_excludes_free_text_and_transaction_values(complete_run: Path) -> None:
    survey_fields = {column["name"] for column in safe_columns("satisfaction_surveys")}
    transaction_fields = {column["name"] for column in safe_columns("transactions")}
    assert not {"question_1_text", "question_2_text", "question_3_text", "open_comments"} & survey_fields
    assert not {"amount", "amount_usd", "fraud_score", "is_fraud", "transaction_city"} & transaction_fields
    rows = sample_rows(complete_run, "transactions", "clean", 25)
    assert rows
    assert not {"amount", "amount_usd", "fraud_score", "transaction_city"} & rows[0].keys()
    assert "transaction_date_month" in rows[0]


def test_relationship_map_classifies_coverage_and_semantic_mismatches(complete_run: Path) -> None:
    rows = relationship_rows(complete_run)
    customer_product = next(row for row in rows if row["child"] == "products" and row["column"] == "customer_id")
    complaint_product = next(
        row for row in rows if row["child"] == "complaints" and row["column"] == "affected_product_id"
    )
    complaint_origin = next(
        row for row in rows if row["child"] == "complaints" and row["column"] == "origin_interaction_id"
    )
    assert customer_product["status"] == "green"
    assert complaint_product["status"] == "red"
    assert complaint_origin["status"] == "gray"
    alerts = relationship_alerts(rows)
    assert {row["finding"] for row in alerts} >= {"different_customer_owner", "no_origin_ids"}
    dot = graph_dot(rows, {"customers": 2, "products": 1})
    assert "digraph relations" in dot
    assert "#c62828" in dot


def test_workflow_assessments_preserve_each_dimension(complete_run: Path) -> None:
    workflows = {row["workflow"]: row for row in workflow_assessments(complete_run)}
    assert not workflows["accounts_payments"]["project_choice"]
    assert workflows["disputes"]["project_choice"]
    assert {row["dimension"] for row in workflows["accounts_payments"]["dimensions"]} == {
        "data_availability",
        "join_integrity",
        "demand_evidence",
        "evaluation_readiness",
        "policy_safety",
    }
    dispute = {row["dimension"]: row["status"] for row in workflows["disputes"]["dimensions"]}
    assert dispute["join_integrity"] == "red"
    assert dispute["evaluation_readiness"] == "red"
    assert "score" not in workflows["accounts_payments"]


def test_sample_without_warehouse_is_unavailable(tmp_path: Path) -> None:
    assert sample_rows(tmp_path, "customers", "clean", 25) == []


@pytest.mark.parametrize("page_name", ["inventory", "profile", "curate", "analyze", "report"])
def test_viewer_pages_read_only_aggregates(complete_run: Path, page_name: str) -> None:
    from streamlit.testing.v1 import AppTest

    script = (
        "from pathlib import Path\n"
        f"from bank_data.eda.ui import {page_name}_page\n"
        "import streamlit as st\n"
        "st.session_state['language']='Español'\n"
        f"{page_name}_page(Path({str(complete_run)!r}))\n"
    )
    result = AppTest.from_string(script).run(timeout=30)
    assert not result.exception
    assert "Consulta sintética" not in str(result)


@pytest.mark.parametrize("page_name", ["explore", "relations", "decide"])
def test_laboratory_pages_render_without_private_values(complete_run: Path, page_name: str) -> None:
    from streamlit.testing.v1 import AppTest

    function = {"explore": "explore_page", "relations": "relations_page", "decide": "decide_page"}[page_name]
    script = (
        "from pathlib import Path\n"
        f"from bank_data.eda.ui import {function}\n"
        "import streamlit as st\n"
        "st.session_state['language']='Español'\n"
        f"{function}(Path({str(complete_run)!r}))\n"
    )
    result = AppTest.from_string(script).run(timeout=30)
    assert not result.exception
    assert "undefined" not in str(result).lower()
    assert "Consulta sintética" not in str(result)


def test_viewer_empty_state_and_inventory_navigation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from streamlit.testing.v1 import AppTest

    script = "from bank_data.eda.ui import main\nmain()\n"
    monkeypatch.chdir(tmp_path)
    empty = AppTest.from_string(script).run(timeout=30)
    assert not empty.exception
    assert "make eda" in empty.info[0].value
    source = tmp_path / "data"
    csv_file(source, "branches", [row("branches")])
    inventory(source, source / "eda")
    result = AppTest.from_string(script).run(timeout=30)
    assert not result.exception
    assert len(result.metric) == 3
    result.sidebar.selectbox[0].set_value("English").run()
    assert not result.exception
    assert result.title[0].value == "Banking dataset exploration"


def test_ingestion_checkpoint_reuses_committed_files_without_duplicates(source: Path, tmp_path: Path) -> None:
    from bank_data.eda.profile import ingest

    run = inventory(source, tmp_path / "out")
    manifest = read_json(run / "manifest.json")
    connection = connect(run)
    first = {**manifest, "files": manifest["files"][:3]}
    ingest(connection, first, run)
    count_before = connection.execute("SELECT count(*) FROM raw.call_center_interactions").fetchone()[0]
    ingest(connection, manifest, run)
    assert connection.execute("SELECT count(*) FROM raw.call_center_interactions").fetchone()[0] == count_before
    assert connection.execute("SELECT count(*) FROM meta.ingested_files").fetchone()[0] == 13
    connection.close()


def test_failed_batch_rolls_back_good_files_before_retry(tmp_path: Path) -> None:
    source = tmp_path / "source"
    csv_file(source, "transactions", [row("transactions", transaction_id="good1")], "transactions/a.csv")
    bad = csv_file(source, "transactions", [row("transactions")], "transactions/b.csv")
    with bad.open("a") as stream:
        stream.write('"unterminated field\n')
    csv_file(source, "transactions", [row("transactions", transaction_id="good2")], "transactions/c.csv")
    run = inventory(source, tmp_path / "out")
    profile(run)
    data = read_json(run / "profile.json")
    assert data["tables"][0]["rows"] == 2
    assert len(data["file_errors"]) == 1
    verify_inputs(run)


def test_schema_additions_are_preserved_and_do_not_hide_conflicts(tmp_path: Path) -> None:
    source = tmp_path / "source"
    path = csv_file(source, "transactions", [row("transactions")])
    with path.open(newline="") as stream:
        content = list(csv.reader(stream))
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow([*content[0], "source_revision"])
        writer.writerow([*content[1], "old"])
        writer.writerow([*content[1], "new"])
    run = inventory(source, tmp_path / "out")
    profile(run)
    curate(run)
    stats = read_json(run / "curate.json")["tables"][0]
    assert stats["conflicting_key"] == 2
    assert stats["clean_rows"] == 0
    with connect(run) as connection:
        assert connection.execute("SELECT count(DISTINCT source_revision) FROM raw.transactions").fetchone()[0] == 2


def test_normalized_text_groups_do_not_drop_distinct_events(source: Path, tmp_path: Path) -> None:
    texts = ["CONSULTA SINTÉTICA", "consulta sinte\u0301tica", "  consulta   sintética  "]
    csv_file(
        source,
        "call_transcripts",
        [
            row(
                "call_transcripts",
                transcript_id=f"t{i}",
                interaction_id=f"i{i}",
                customer_text=text,
                full_text=text,
                mentioned_entities="{}",
            )
            for i, text in enumerate(texts, start=1)
        ],
    )
    run = inventory(source, tmp_path / "out")
    profile(run)
    curate(run)
    analyze(run)
    summary = read_json(run / "analyze.json")["text"]["summary"]
    assert summary["rows_with_customer_text"] == 3
    assert summary["exact_groups"] == 3
    assert summary["normalized_groups"] == 1
