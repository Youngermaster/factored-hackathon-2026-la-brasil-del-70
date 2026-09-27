"""A contract-suite backend for the DuckDB readers: the contract dataset written as gold serving Parquet.

The files use ``GOLD_SCHEMAS``, the same serving contract the dbt gold models write (checked by the data
platform integration tests), so the suites exercise the adapter exactly as it reads real gold output.
"""

import tempfile
from collections.abc import AsyncIterator, Iterable, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb

from bank_agent.adapters.persistence.duckdb.gold import GOLD_SCHEMAS, gold_file
from bank_agent.adapters.persistence.duckdb.readers import DuckDbGoldStore
from bank_agent.domain.access import AccessContext
from bank_agent.domain.locale import Country
from bank_agent.domain.money import Money
from bank_agent_contracts import ContractDataset, Readers

SNAPSHOT = date(2026, 5, 31)


def _naive(value: datetime | None) -> datetime | None:
    return None if value is None else value.astimezone(UTC).replace(tzinfo=None)


def _amount(money: Money | None) -> object:
    return None if money is None else money.amount


def _currency(money: Money | None) -> str | None:
    return None if money is None else money.currency.value


def write_table(gold_dir: Path, table: str, rows: Iterable[Sequence[object]]) -> None:
    columns = GOLD_SCHEMAS[table]
    connection = duckdb.connect()
    try:
        definition = ", ".join(f"{name} {sql_type}" for name, sql_type in columns)
        connection.execute(f"create table staged ({definition})")
        placeholders = ", ".join("?" for _ in columns)
        batch = [list(row) for row in rows]
        if batch:
            connection.executemany(f"insert into staged values ({placeholders})", batch)  # noqa: S608
        target = gold_file(gold_dir, table).as_posix()
        connection.execute(f"copy staged to '{target}' (format parquet)")
    finally:
        connection.close()


def write_gold(gold_dir: Path, data: ContractDataset) -> None:
    write_table(
        gold_dir,
        "customers_serving",
        (
            (
                item.customer_id,
                item.first_name,
                item.country.value,
                item.segment.value,
                item.status.value,
                None,
                None,
                None,
                SNAPSHOT,
            )
            for item in data.customers
        ),
    )
    write_table(
        gold_dir,
        "products_serving",
        (
            (
                item.product_id,
                item.customer_id,
                item.product_type.value,
                item.status.value,
                item.masked_number.last4,
                item.currency.value,
                _amount(item.current_balance),
                _amount(item.credit_limit),
                item.annual_interest_rate,
                item.opened_on,
                item.expires_on,
                item.days_past_due,
                _naive(item.balance_as_of),
                True,
                item.is_card,
                item.is_credit_product,
                SNAPSHOT,
            )
            for item in data.products
        ),
    )
    write_table(
        gold_dir,
        "transactions_serving",
        (
            (
                item.transaction_id,
                item.customer_id,
                item.product_id,
                _naive(item.occurred_at),
                item.occurred_at.date(),
                item.transaction_type.value,
                None if item.category is None else item.category.value,
                item.amount.amount,
                item.amount.currency.value,
                _amount(item.amount_usd),
                False,
                item.channel.value,
                item.status.value,
                "00",
                item.merchant_name,
                item.merchant_category,
                item.location_country,
                item.location_city,
                item.fraud.label,
                item.fraud.score,
            )
            for item in data.transactions
        ),
    )
    write_table(
        gold_dir,
        "complaints_serving",
        (
            (
                item.complaint_id,
                item.customer_id,
                _naive(item.created_at),
                item.created_at.date(),
                item.case_type.value,
                item.category,
                item.subcategory,
                item.reception_channel.value,
                item.affected_product_id,
                _amount(item.claimed_amount),
                _currency(item.claimed_amount),
                item.priority.value,
            )
            for item in data.complaints
        ),
    )
    write_table(
        gold_dir,
        "credit_profiles_serving",
        (
            (
                item.customer_id,
                item.credit_score,
                _amount(item.estimated_monthly_income),
                _currency(item.estimated_monthly_income) or Country.MX.default_currency.value,
                item.tenure_months,
                item.credit_product_count,
                item.max_days_past_due,
                _amount(item.total_credit_limit),
                _currency(item.total_credit_limit),
                item.utilization,
                item.as_of,
            )
            for item in data.credit_profiles
        ),
    )


class DuckDbBackend:
    """The DuckDB readers over gold Parquet in a temporary directory. Read only."""

    def __init__(self) -> None:
        self._directory = tempfile.TemporaryDirectory(prefix="gold-contract-")
        self._store: DuckDbGoldStore | None = None

    async def seed(self, data: ContractDataset) -> None:
        gold_dir = Path(self._directory.name)
        write_gold(gold_dir, data)
        self._store = DuckDbGoldStore(gold_dir)

    def readers(self, context: AccessContext) -> AbstractAsyncContextManager[Readers]:
        @asynccontextmanager
        async def _open() -> AsyncIterator[Readers]:
            if self._store is None:
                raise RuntimeError("seed the backend first")
            yield self._store.readers(context)

        return _open()

    async def aclose(self) -> None:
        if self._store is not None:
            self._store.close()
        self._directory.cleanup()
