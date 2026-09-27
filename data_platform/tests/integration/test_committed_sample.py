"""The committed-sample extractor on the fixture's bronze, and the committed sample itself."""

import csv
import io
from datetime import date
from pathlib import Path

import pytest

from bank_data import pipeline
from bank_data.contracts.tables import TABLES, table_spec
from bank_data.errors import ConfigurationError, SampleError
from bank_data.ingest.local import LocalSource
from bank_data.ingest.runner import IngestRunner
from bank_data.sample.build import build_sample, dataset_version
from bank_data.sample.extract import (
    SampleExtractor,
    SampleSettings,
    layout_files,
    preview_files,
    pseudonymize,
    sample_rank,
    write_sample,
)
from bank_data.sample.readme import REQUIRED_SECTIONS, DatasetVersion, render_readme
from bank_data.settings import DEFAULT_SAMPLE_DIR
from bank_data_fixture import FIXTURE_ROOT, workspace

SNAPSHOT = date(2026, 6, 17)
FIXTURE_COVERAGE = ("credit_card", "debit_card", "deposit_with_balance", "income_present", "income_missing")
SETTINGS = SampleSettings(
    min_customers=2,
    min_complaints=0,
    window_days=10_000,
    required_coverage=FIXTURE_COVERAGE,
    allow_whole_tables=True,
)
"""The fixture's dimension tables hold one to three rows, so a sample of them is necessarily whole."""


@pytest.fixture(scope="module")
def bronze_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    warehouse = tmp_path_factory.mktemp("sample_bronze")
    report = IngestRunner(LocalSource(FIXTURE_ROOT / "base"), warehouse, snapshot_date=SNAPSHOT).run()
    assert report.exit_code == 0
    return warehouse / "bronze"


def _files(bronze_dir: Path, settings: SampleSettings = SETTINGS) -> dict[str, str]:
    result = SampleExtractor(bronze_dir, SNAPSHOT, settings).extract()
    tables = pseudonymize(result.tables)
    return layout_files(tables) | preview_files(tables, settings.preview_rows)


def test_extraction_is_deterministic_to_the_byte(bronze_dir: Path, tmp_path: Path) -> None:
    first, second = _files(bronze_dir), _files(bronze_dir)
    assert first == second
    write_sample(tmp_path / "a", first)
    write_sample(tmp_path / "a", second)
    written = {
        path.relative_to(tmp_path / "a").as_posix(): path.read_bytes() for path in (tmp_path / "a").rglob("*.csv")
    }
    assert written == {path: content.encode("utf-8") for path, content in first.items()}


def test_customers_follow_the_seeded_ranking_and_every_table_follows_them(bronze_dir: Path) -> None:
    result = SampleExtractor(bronze_dir, SNAPSHOT, SETTINGS).extract()
    ranked = sorted(
        ["CLI-FIX-0001", "CLI-FIX-0002", "CLI-FIX-0003", "CLI-FIX-0004"],
        key=lambda item: sample_rank(SETTINGS.seed, item),
    )
    assert result.customers == ranked[: len(result.customers)]
    chosen = set(result.customers)
    for spec in TABLES:
        if spec.customer_column is not None:
            assert {row[spec.customer_column].strip() for row in result.tables[spec.name]} <= chosen


def test_referential_closure_keeps_references_inside_the_sample(bronze_dir: Path) -> None:
    tables = SampleExtractor(bronze_dir, SNAPSHOT, SETTINGS).extract().tables
    products = {row["product_id"] for row in tables["products"]}
    interactions = {row["interaction_id"] for row in tables["call_center_interactions"]}
    agents = {row["agent_id"] for row in tables["service_agents"]}
    branches = {row["branch_id"] for row in tables["branches"]}
    assert {row["product_id"] for row in tables["transactions"]} <= products
    assert {row["interaction_id"] for row in tables["call_transcripts"]} <= interactions
    assert {row["agent_id"] for row in tables["call_center_interactions"]} <= agents
    assert {row["opening_branch_id"] for row in tables["products"]} <= branches
    assert "BR-FIX-999" not in branches
    for row in tables["daily_exchange_rates"]:
        assert row["target_currency"] == "USD"


def test_pseudonymization_replaces_every_direct_identifier(bronze_dir: Path) -> None:
    original = SampleExtractor(bronze_dir, SNAPSHOT, SETTINGS).extract().tables
    text = "\n".join(_files(bronze_dir).values())
    identifiers = {
        row[column.name]
        for spec in TABLES
        for column in spec.columns
        if column.pii is not None
        for row in original[spec.name]
        if row[column.name].strip()
    }
    assert identifiers
    leaked = sorted(value for value in identifiers if value in text)
    assert leaked == []
    customers = list(csv.DictReader(io.StringIO(_files(bronze_dir)["customers.csv"].lstrip("﻿"))))
    assert all(row["email"].endswith("@example.com") for row in customers if row["email"])
    phones = [row["mobile_phone"] for row in customers if row["mobile_phone"]]
    assert all(phone.startswith(("+52 ", "+57 ", "+54 ")) for phone in phones)


def test_pseudonymized_files_still_pass_the_contracts(bronze_dir: Path, tmp_path: Path) -> None:
    sample_dir = tmp_path / "sample"
    write_sample(sample_dir, _files(bronze_dir))
    report = IngestRunner(LocalSource(sample_dir), tmp_path / "wh", snapshot_date=SNAPSHOT).run()
    assert report.exit_code == 0
    assert report.counts()["rows_quarantined"] == 0
    assert report.skipped == 0


def test_row_cap_and_coverage_failures_stop_the_extraction(bronze_dir: Path) -> None:
    with pytest.raises(SampleError, match="above the limit"):
        SampleExtractor(bronze_dir, SNAPSHOT, SampleSettings(**{**SETTINGS.__dict__, "row_limit": 10})).extract()
    with pytest.raises(SampleError, match="whole branches table"):
        SampleExtractor(
            bronze_dir, SNAPSHOT, SampleSettings(**{**SETTINGS.__dict__, "allow_whole_tables": False})
        ).extract()
    with pytest.raises(SampleError, match="payment_pending"):
        SampleExtractor(
            bronze_dir, SNAPSHOT, SampleSettings(**{**SETTINGS.__dict__, "required_coverage": ("payment_pending",)})
        ).extract()


def test_readme_documents_provenance_counts_treatments_and_examples(bronze_dir: Path) -> None:
    result = SampleExtractor(bronze_dir, SNAPSHOT, SETTINGS).extract()
    tables = pseudonymize(result.tables)
    version = DatasetVersion("fixture", "2026-06-17", (("customers.csv", "etag"),), (("transactions", 2, "abc"),))
    text = render_readme(tables, 10, version, SETTINGS, len(result.customers), result.coverage)
    for section in REQUIRED_SECTIONS:
        assert section in text
    for spec in TABLES:
        assert f"| {spec.name} | {len(tables[spec.name])} |" in text
        assert f"### {spec.name}" in text
    assert "document_number" in text
    assert "organizer-provided synthetic data" in text.lower()


def test_the_committed_sample_ingests_cleanly_without_network(tmp_path: Path) -> None:
    space = workspace(DEFAULT_SAMPLE_DIR, tmp_path / "wh")
    report = pipeline.ingest(space)
    assert report.exit_code == 0
    assert report.counts()["rows_quarantined"] == 0
    assert report.skipped == 0
    assert table_spec("customers").name in {
        key.split(".")[0] for key in (obj.key for obj in space.data_source().list_objects())
    }


def test_build_sample_writes_files_preview_and_a_readme_the_guard_accepts(tmp_path: Path) -> None:
    import importlib.util
    import sys

    space = workspace(FIXTURE_ROOT / "base", tmp_path / "wh")
    assert pipeline.ingest(space).exit_code == 0
    output = tmp_path / "sample"

    result = build_sample(space, output, SETTINGS)

    assert (output / "README.md").is_file()
    assert (output / "preview" / "customers.csv").is_file()
    assert len(result.customers) >= SETTINGS.min_customers
    version = dataset_version(space)
    assert version.snapshot_date == "2026-06-17"
    assert ("transactions", 2) in {(table, count) for table, count, _ in version.partition_digests}
    assert len(version.snapshot_etags) == 6
    script = Path(__file__).resolve().parents[3] / "scripts" / "checks" / "check_data_sample.py"
    spec = importlib.util.spec_from_file_location("check_data_sample_it", script)
    assert spec is not None
    assert spec.loader is not None
    guard = importlib.util.module_from_spec(spec)
    sys.modules["check_data_sample_it"] = guard
    spec.loader.exec_module(guard)
    assert guard.check(output) == []


def test_dataset_version_needs_a_manifest(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="no manifest"):
        dataset_version(workspace(FIXTURE_ROOT / "base", tmp_path / "empty"))
