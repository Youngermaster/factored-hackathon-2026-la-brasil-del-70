"""Update correctness on the synthetic late-arrival fixture (``data_platform/fixtures/late_arrival``)."""

from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from bank_agent.adapters.persistence.duckdb.gold import DATASET_CREDIT_BALANCE_CONVENTION, GOLD_SCHEMAS
from bank_agent.adapters.persistence.duckdb.readers import DuckDbGoldStore
from bank_agent.domain.access import AccessContext
from bank_agent.domain.accounts import BalanceView
from bank_agent.domain.identifiers import CustomerId, ProductId
from bank_agent.domain.locale import Country
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.product import ProductType
from bank_agent.domain.transaction import TransactionType
from bank_agent.ports.repositories.transactions import TransactionQuery
from bank_data import pipeline
from bank_data.errors import SchemaEvolutionError
from bank_data.ingest.manifest import Manifest, ObjectStatus
from bank_data_fixture import copy_parts, ingest_and_build, table_hashes, workspace

LATE_KEY = "transactions/year=2024/month=01/day=02/transactions_20240102.csv"
BREAKING_KEY = "transactions/year=2024/month=01/day=04/transactions_20240104.csv"


@pytest.fixture(scope="module")
def incremental_and_full(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Warehouse A: base, build, late partition, incremental build. Warehouse B: base plus late, full build."""
    root = tmp_path_factory.mktemp("update_correctness")
    source_a = copy_parts(root / "source_a", "base")
    space_a = workspace(source_a, root / "warehouse_a")
    ingest_and_build(space_a)
    copy_parts(source_a, "late")
    late_report = ingest_and_build(space_a)
    assert (late_report.new, late_report.unchanged) == (1, 18)

    source_b = copy_parts(root / "source_b", "base", "late")
    space_b = workspace(source_b, root / "warehouse_b")
    ingest_and_build(space_b, full_refresh=True)
    return space_a.dbt_target().warehouse_db, space_b.dbt_target().warehouse_db


def test_incremental_build_after_a_late_partition_equals_a_full_rebuild(
    incremental_and_full: tuple[Path, Path],
) -> None:
    incremental, full = (table_hashes(path) for path in incremental_and_full)

    assert incremental.keys() == full.keys()
    assert "silver.stg_transactions" in incremental
    assert "gold.transactions_serving" in incremental
    mismatched = sorted(name for name in full if incremental[name] != full[name])
    assert mismatched == []


def test_late_partition_rows_and_duplicates_resolve_as_documented(incremental_and_full: tuple[Path, Path]) -> None:
    connection = duckdb.connect(str(incremental_and_full[0]), read_only=True)
    try:
        rows = dict(
            connection.execute(
                "select transaction_id, transaction_status from silver.stg_transactions order by 1"
            ).fetchall()
        )
        exact_duplicates = connection.execute(
            "select count(*) from silver.stg_transactions where transaction_id = 'TRX-FIX-0001'"
        ).fetchone()
        segment = connection.execute(
            "select segment from silver.stg_customers where customer_id = 'CLI-FIX-0002'"
        ).fetchone()
        recomputed = connection.execute(
            "select amount_usd, amount_usd_recomputed from silver.silver_transactions where transaction_id = ?",
            ["TRX-FIX-0003"],
        ).fetchone()
    finally:
        connection.close()
    assert {"TRX-FIX-0020", "TRX-FIX-0021", "TRX-FIX-0022"} <= rows.keys()
    assert rows["TRX-FIX-0003"] == "approved"
    assert rows["TRX-FIX-0010"] == "approved"
    assert exact_duplicates == (1,)
    assert segment == ("premium",)
    assert recomputed is not None
    assert str(recomputed[0]) == "37.50"
    assert recomputed[1] is True


def test_breaking_type_change_is_quarantined_and_the_run_fails(tmp_path: Path) -> None:
    source = copy_parts(tmp_path / "source", "base", "breaking")
    space = workspace(source, tmp_path / "warehouse")

    report = pipeline.ingest(space)

    assert report.exit_code == SchemaEvolutionError.exit_code == 3
    assert report.outstanding_quarantined == ((BREAKING_KEY, "schema_type_change"),)
    with Manifest(space.manifest_path) as manifest:
        assert manifest.status_of(BREAKING_KEY) is ObjectStatus.QUARANTINED
    quarantined = duckdb.execute(
        "select _reason_code, _column, count(*) from read_parquet(?) group by all",
        [(space.warehouse_dir / "quarantine" / "transactions" / "**" / "*.parquet").as_posix()],
    ).fetchall()
    assert quarantined == [("schema_type_change", "amount", 3)]
    assert pipeline.ingest(space).exit_code == 3


def test_additive_column_is_accepted_into_bronze_and_recorded(tmp_path: Path) -> None:
    source = copy_parts(tmp_path / "source", "base")
    space = workspace(source, tmp_path / "warehouse")

    report = pipeline.ingest(space)

    assert report.exit_code == 0
    bronze = duckdb.execute(
        "select complaint_id, channel_detail from read_parquet(?, union_by_name = true) order by complaint_id",
        [(space.bronze_dir / "complaints" / "**" / "*.parquet").as_posix()],
    ).fetchall()
    assert bronze == [("CMP-FIX-0001", None), ("CMP-FIX-0002", "portal")]
    connection = duckdb.connect(str(space.manifest_path), read_only=True)
    try:
        events = connection.execute("select kind, reason_code, added from schema_events").fetchall()
        backlog = connection.execute("select table_name, column_name from backlog_items").fetchall()
    finally:
        connection.close()
    assert events == [("additive", "schema_additive_column", "channel_detail")]
    assert backlog == [("complaints", "channel_detail")]


def test_gold_serving_files_match_the_adapter_contract(incremental_and_full: tuple[Path, Path]) -> None:
    gold_dir = incremental_and_full[0].parent / "gold"
    for table, columns in GOLD_SCHEMAS.items():
        described = duckdb.execute(
            "select column_name, column_type from (describe select * from read_parquet(?))",
            [(gold_dir / f"{table}.parquet").as_posix()],
        ).fetchall()
        assert [(str(name), str(kind)) for name, kind in described] == list(columns), table


async def test_bank_agent_readers_serve_the_fixture_gold_output(incremental_and_full: tuple[Path, Path]) -> None:
    store = DuckDbGoldStore(incremental_and_full[0].parent / "gold")
    try:
        readers = store.readers(AccessContext.for_customer(CustomerId("CLI-FIX-0001")))
        customer = await readers.customers.get_current()
        products = await readers.products.list()
        card = await readers.products.get(ProductId("PRD-FIX-CC01"))
        payments = await readers.transactions.list(TransactionQuery(types=(TransactionType.PAYMENT,)))
        profile = await readers.credit_profiles.get_mine()
        insured = await store.readers(AccessContext.for_customer(CustomerId("CLI-FIX-0004"))).products.list()
    finally:
        store.close()
    assert (customer.first_name, customer.country) == ("Ana", Country.MX)
    assert [product.product_id for product in products] == ["PRD-FIX-CC01", "PRD-FIX-DC01", "PRD-FIX-SV01"]
    assert card is not None
    assert str(card.masked_number) == "**** 0001"
    assert card.current_balance == Money.of("1200.50", Currency.USD)
    view = BalanceView.from_product(card, DATASET_CREDIT_BALANCE_CONVENTION)
    assert view.available_credit == Money.of("3799.50", Currency.USD)
    assert [txn.transaction_id for txn in payments] == ["TRX-FIX-0002"]
    assert profile is not None
    assert profile.utilization == Decimal("0.2401")
    assert insured[0].product_type is ProductType.OTHER
