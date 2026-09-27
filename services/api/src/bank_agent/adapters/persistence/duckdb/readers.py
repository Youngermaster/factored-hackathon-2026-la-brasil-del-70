"""DuckDB readers over the gold serving Parquet: customers, products, transactions, complaints, credit profiles.

Read only. Every reader is bound to an ``AccessContext`` and filters by the context customer in SQL, so
another customer's record behaves exactly like a missing one; staff contexts raise ``AccessContextError``
exactly like the in-memory adapters (the shared contract suites run against both). Queries use bound
parameters only. Rows become domain objects here: nothing outside this module sees a DuckDB row.
"""

from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

from bank_agent.adapters.persistence.duckdb.gold import open_gold
from bank_agent.domain.access import AccessContext, Role
from bank_agent.domain.complaint import ComplaintCaseType, ComplaintChannel, HistoricalComplaint, Priority
from bank_agent.domain.credit import CreditProfile
from bank_agent.domain.customer import Customer, CustomerSegment, CustomerStatus
from bank_agent.domain.errors import AccessContextError, CustomerNotFoundError
from bank_agent.domain.identifiers import ComplaintId, CustomerId, ProductId, TransactionId
from bank_agent.domain.locale import Country
from bank_agent.domain.masking import MaskedNumber
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.product import Product, ProductStatus, ProductType
from bank_agent.domain.transaction import (
    FraudContext,
    Transaction,
    TransactionCategory,
    TransactionChannel,
    TransactionStatus,
    TransactionType,
)
from bank_agent.ports.repositories.transactions import TransactionQuery

Row = dict[str, Any]
_PRODUCT_TYPES = {member.value for member in ProductType}


def _customer_of(context: AccessContext) -> CustomerId:
    if context.role is not Role.CUSTOMER or context.customer_id is None:
        raise AccessContextError("this operation needs a customer context")
    return context.customer_id


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _money(amount: Decimal | None, currency: str | None) -> Money | None:
    if amount is None or currency is None:
        return None
    return Money.of(amount, Currency(currency))


class _GoldQueries:
    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self._connection = connection

    def rows(self, sql: str, parameters: Sequence[object]) -> list[Row]:
        cursor = self._connection.cursor()
        try:
            result = cursor.execute(sql, list(parameters))
            names = [column[0] for column in result.description or ()]
            return [dict(zip(names, values, strict=True)) for values in result.fetchall()]
        finally:
            cursor.close()


class DuckDbCustomerReader:
    def __init__(self, queries: _GoldQueries, context: AccessContext) -> None:
        self._queries = queries
        self._context = context

    async def get_current(self) -> Customer:
        rows = self._queries.rows(
            "select * from customers_serving where customer_id = ?", [_customer_of(self._context)]
        )
        if not rows:
            raise CustomerNotFoundError()
        row = rows[0]
        return Customer(
            customer_id=CustomerId(row["customer_id"]),
            country=Country(row["country"]),
            segment=CustomerSegment(row["segment"]),
            status=CustomerStatus(row["customer_status"]),
            first_name=row["first_name"],
        )


def product_from_row(row: Row) -> Product:
    currency = Currency(row["currency"])
    product_type = row["product_type"]
    return Product(
        product_id=ProductId(row["product_id"]),
        customer_id=CustomerId(row["customer_id"]),
        product_type=ProductType(product_type) if product_type in _PRODUCT_TYPES else ProductType.OTHER,
        status=ProductStatus(row["product_status"]),
        masked_number=MaskedNumber(last4=row["product_number_last4"]),
        currency=currency,
        current_balance=_money(row["current_balance"], currency.value),
        credit_limit=_money(row["credit_limit"], currency.value),
        annual_interest_rate=row["interest_rate"],
        opened_on=row["opening_date"],
        expires_on=row["expiration_date"],
        balance_as_of=_utc(row["balance_as_of"]),
        days_past_due=row["days_past_due"],
    )


class DuckDbProductReader:
    def __init__(self, queries: _GoldQueries, context: AccessContext) -> None:
        self._queries = queries
        self._context = context

    async def get(self, product_id: ProductId) -> Product | None:
        rows = self._queries.rows(
            "select * from products_serving where customer_id = ? and product_id = ?",
            [_customer_of(self._context), product_id],
        )
        return product_from_row(rows[0]) if rows else None

    async def list(self, types: frozenset[ProductType] | None = None) -> Sequence[Product]:
        rows = self._queries.rows(
            "select * from products_serving where customer_id = ? order by product_id", [_customer_of(self._context)]
        )
        products = [product_from_row(row) for row in rows]
        return [product for product in products if types is None or product.product_type in types]


def transaction_from_row(row: Row) -> Transaction:
    category = row["transaction_category"]
    occurred_at = _utc(row["transaction_at"])
    if occurred_at is None:
        raise ValueError("a served transaction always has a timestamp")
    return Transaction(
        transaction_id=TransactionId(row["transaction_id"]),
        customer_id=CustomerId(row["customer_id"]),
        product_id=ProductId(row["product_id"]),
        occurred_at=occurred_at,
        transaction_type=TransactionType(row["transaction_type"]),
        category=TransactionCategory(category) if category is not None else None,
        amount=Money.of(row["amount"], Currency(row["currency"])),
        amount_usd=_money(row["amount_usd"], Currency.USD.value),
        channel=TransactionChannel(row["channel"]),
        status=TransactionStatus(row["transaction_status"]),
        merchant_name=row["merchant_name"],
        merchant_category=row["merchant_category"],
        location_country=row["location_country"],
        location_city=row["location_city"],
        fraud=FraudContext(label=bool(row["is_fraud"]), score=row["fraud_score"]),
    )


class DuckDbTransactionReader:
    def __init__(self, queries: _GoldQueries, context: AccessContext) -> None:
        self._queries = queries
        self._context = context

    async def get(self, transaction_id: TransactionId) -> Transaction | None:
        rows = self._queries.rows(
            "select * from transactions_serving where customer_id = ? and transaction_id = ?",
            [_customer_of(self._context), transaction_id],
        )
        return transaction_from_row(rows[0]) if rows else None

    async def list(self, query: TransactionQuery) -> Sequence[Transaction]:
        clauses = ["customer_id = ?"]
        parameters: list[object] = [_customer_of(self._context)]
        if query.occurred_from is not None:
            clauses.append("transaction_at >= ?")
            parameters.append(query.occurred_from.astimezone(UTC).replace(tzinfo=None))
        if query.occurred_to is not None:
            clauses.append("transaction_at <= ?")
            parameters.append(query.occurred_to.astimezone(UTC).replace(tzinfo=None))
        for column, values in (
            ("product_id", list(query.product_ids)),
            ("transaction_status", [status.value for status in query.statuses]),
            ("transaction_type", [kind.value for kind in query.types]),
        ):
            if values:
                clauses.append(f"{column} in ({', '.join('?' for _ in values)})")
                parameters.extend(values)
        if query.min_amount is not None:
            clauses.append("amount >= ?")
            parameters.append(query.min_amount)
        if query.max_amount is not None:
            clauses.append("amount <= ?")
            parameters.append(query.max_amount)
        parameters.append(query.limit)
        sql = (
            "select * from transactions_serving where "  # noqa: S608  # nosec B608 (fixed column names; values are bound)
            + " and ".join(clauses)
            + " order by transaction_at desc, transaction_id asc limit ?"
        )
        return [transaction_from_row(row) for row in self._queries.rows(sql, parameters)]


def complaint_from_row(row: Row) -> HistoricalComplaint:
    created_at = _utc(row["created_at"])
    if created_at is None:
        raise ValueError("a served complaint always has a creation instant")
    return HistoricalComplaint(
        complaint_id=ComplaintId(row["complaint_id"]),
        customer_id=CustomerId(row["customer_id"]),
        created_at=created_at,
        case_type=ComplaintCaseType(row["case_type"]),
        category=row["category"],
        subcategory=row["subcategory"],
        reception_channel=ComplaintChannel(row["reception_channel"]),
        affected_product_id=ProductId(row["affected_product_id"]) if row["affected_product_id"] else None,
        claimed_amount=_money(row["claimed_amount"], row["currency"]),
        priority=Priority(row["priority"]),
    )


class DuckDbHistoricalComplaintReader:
    def __init__(self, queries: _GoldQueries, context: AccessContext) -> None:
        self._queries = queries
        self._context = context

    async def list_since(self, since: datetime) -> Sequence[HistoricalComplaint]:
        rows = self._queries.rows(
            "select * from complaints_serving where customer_id = ? and created_at >= ? "
            "order by created_at desc, complaint_id asc",
            [_customer_of(self._context), since.astimezone(UTC).replace(tzinfo=None)],
        )
        return [complaint_from_row(row) for row in rows]

    async def count_since(self, since: datetime) -> int:
        rows = self._queries.rows(
            "select count(*) as found from complaints_serving where customer_id = ? and created_at >= ?",
            [_customer_of(self._context), since.astimezone(UTC).replace(tzinfo=None)],
        )
        return int(rows[0]["found"])


def credit_profile_from_row(row: Row) -> CreditProfile:
    as_of: date = row["snapshot_date"]
    return CreditProfile(
        customer_id=CustomerId(row["customer_id"]),
        credit_score=row["credit_score"],
        estimated_monthly_income=_money(row["estimated_monthly_income"], row["income_currency"]),
        tenure_months=row["tenure_months"],
        credit_product_count=row["credit_product_count"],
        max_days_past_due=row["max_days_past_due"],
        total_credit_limit=_money(row["total_credit_limit"], row["total_credit_limit_currency"]),
        utilization=row["utilization"],
        as_of=as_of,
    )


class DuckDbCreditProfileReader:
    def __init__(self, queries: _GoldQueries, context: AccessContext) -> None:
        self._queries = queries
        self._context = context

    async def get_mine(self) -> CreditProfile | None:
        rows = self._queries.rows(
            "select * from credit_profiles_serving where customer_id = ?", [_customer_of(self._context)]
        )
        return credit_profile_from_row(rows[0]) if rows else None


class DuckDbReaders:
    """The read-side repositories bound to one context (structurally the reader half of a unit of work)."""

    def __init__(self, queries: _GoldQueries, context: AccessContext) -> None:
        self.customers = DuckDbCustomerReader(queries, context)
        self.products = DuckDbProductReader(queries, context)
        self.transactions = DuckDbTransactionReader(queries, context)
        self.complaints = DuckDbHistoricalComplaintReader(queries, context)
        self.credit_profiles = DuckDbCreditProfileReader(queries, context)


class DuckDbGoldStore:
    """Owns the connection to one gold directory and hands out readers bound to a context."""

    def __init__(self, gold_dir: Path) -> None:
        self._connection = open_gold(gold_dir)
        self._queries = _GoldQueries(self._connection)

    def readers(self, context: AccessContext) -> DuckDbReaders:
        return DuckDbReaders(self._queries, context)

    def close(self) -> None:
        self._connection.close()
