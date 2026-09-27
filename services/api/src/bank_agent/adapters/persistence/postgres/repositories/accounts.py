"""Customers, products, transactions, complaints, and credit profiles.

Every query filters by the context customer in SQL, and row-level security filters again.
"""

from collections.abc import Sequence
from datetime import datetime

from bank_agent.adapters.persistence.postgres.mappers.accounts import (
    customer_from_row,
    product_from_row,
    transaction_from_row,
)
from bank_agent.adapters.persistence.postgres.mappers.history import complaint_from_row, credit_profile_from_row
from bank_agent.adapters.persistence.postgres.repositories.access import customer_of
from bank_agent.adapters.persistence.postgres.transaction import Tx
from bank_agent.domain.complaint import HistoricalComplaint
from bank_agent.domain.credit import CreditProfile
from bank_agent.domain.customer import Customer
from bank_agent.domain.errors import ConcurrencyConflictError, CustomerNotFoundError, ProductNotFoundError
from bank_agent.domain.identifiers import ProductId, TransactionId
from bank_agent.domain.product import Product, ProductStatus, ProductType
from bank_agent.domain.transaction import Transaction
from bank_agent.ports.repositories.transactions import TransactionQuery


class PostgresCustomerRepository:
    def __init__(self, tx: Tx) -> None:
        self._tx = tx

    async def get_current(self) -> Customer:
        row = await self._tx.one_or_none(
            "SELECT * FROM app.customers WHERE customer_id = :customer", {"customer": customer_of(self._tx.context)}
        )
        if row is None:
            raise CustomerNotFoundError()
        return customer_from_row(row)


class PostgresProductRepository:
    def __init__(self, tx: Tx) -> None:
        self._tx = tx

    async def get(self, product_id: ProductId) -> Product | None:
        row = await self._tx.one_or_none(
            "SELECT * FROM app.products WHERE customer_id = :customer AND product_id = :product",
            {"customer": customer_of(self._tx.context), "product": product_id},
        )
        return product_from_row(row) if row is not None else None

    async def list(self, types: frozenset[ProductType] | None = None) -> Sequence[Product]:
        rows = await self._tx.rows(
            "SELECT * FROM app.products WHERE customer_id = :customer ORDER BY product_id",
            {"customer": customer_of(self._tx.context)},
        )
        products = [product_from_row(row) for row in rows]
        return [product for product in products if types is None or product.product_type in types]

    async def update_status(
        self, product_id: ProductId, new_status: ProductStatus, *, expected: ProductStatus
    ) -> Product:
        current = await self.get(product_id)
        if current is None:
            raise ProductNotFoundError()
        if current.status is not expected:
            raise ConcurrencyConflictError("the product status changed")
        if current.status is new_status:
            return current
        updated = current.blocked() if new_status is ProductStatus.BLOCKED else current.evolve(status=new_status)
        keys = {"customer": current.customer_id, "product": product_id}
        locked = await self._tx.lock_or_mark_conflicted(
            "SELECT 1 FROM app.products WHERE customer_id = :customer AND product_id = :product "
            "FOR NO KEY UPDATE NOWAIT",
            keys,
        )
        if not locked:
            return updated
        changed = await self._tx.execute(
            "UPDATE app.products SET status = :new, status_changed_at = now() "
            "WHERE customer_id = :customer AND product_id = :product AND status = :expected",
            {**keys, "new": new_status.value, "expected": expected.value},
        )
        if changed != 1:
            raise ConcurrencyConflictError("the product status changed")
        return updated


class PostgresTransactionRepository:
    def __init__(self, tx: Tx) -> None:
        self._tx = tx

    async def get(self, transaction_id: TransactionId) -> Transaction | None:
        row = await self._tx.one_or_none(
            "SELECT * FROM app.transactions WHERE customer_id = :customer AND transaction_id = :txn",
            {"customer": customer_of(self._tx.context), "txn": transaction_id},
        )
        return transaction_from_row(row) if row is not None else None

    async def list(self, query: TransactionQuery) -> Sequence[Transaction]:
        clauses = ["customer_id = :customer"]
        parameters: dict[str, object] = {"customer": customer_of(self._tx.context), "limit": query.limit}
        optional: tuple[tuple[str, str, object], ...] = (
            ("occurred_at >= :occurred_from", "occurred_from", query.occurred_from),
            ("occurred_at <= :occurred_to", "occurred_to", query.occurred_to),
            ("amount >= :min_amount", "min_amount", query.min_amount),
            ("amount <= :max_amount", "max_amount", query.max_amount),
        )
        for clause, name, value in optional:
            if value is not None:
                clauses.append(clause)
                parameters[name] = value
        lists: tuple[tuple[str, list[str]], ...] = (
            ("product_id", list(query.product_ids)),
            ("status", [status.value for status in query.statuses]),
            ("transaction_type", [kind.value for kind in query.types]),
        )
        for column, values in lists:
            if values:
                clauses.append(f"{column} = ANY(:{column}_values)")
                parameters[f"{column}_values"] = values
        sql = (
            "SELECT * FROM app.transactions WHERE "  # noqa: S608  # nosec B608 (fixed column names; values are bound)
            + " AND ".join(clauses)
            + " ORDER BY occurred_at DESC, transaction_id ASC LIMIT :limit"
        )
        return [transaction_from_row(row) for row in await self._tx.rows(sql, parameters)]


class PostgresHistoricalComplaintRepository:
    def __init__(self, tx: Tx) -> None:
        self._tx = tx

    async def list_since(self, since: datetime) -> Sequence[HistoricalComplaint]:
        rows = await self._tx.rows(
            "SELECT * FROM app.historical_complaints WHERE customer_id = :customer AND created_at >= :since "
            "ORDER BY created_at DESC, complaint_id ASC",
            {"customer": customer_of(self._tx.context), "since": since},
        )
        return [complaint_from_row(row) for row in rows]

    async def count_since(self, since: datetime) -> int:
        found = await self._tx.scalar(
            "SELECT count(*) FROM app.historical_complaints WHERE customer_id = :customer AND created_at >= :since",
            {"customer": customer_of(self._tx.context), "since": since},
        )
        return int(str(found))


class PostgresCreditProfileReader:
    def __init__(self, tx: Tx) -> None:
        self._tx = tx

    async def get_mine(self) -> CreditProfile | None:
        row = await self._tx.one_or_none(
            "SELECT * FROM app.credit_profiles WHERE customer_id = :customer",
            {"customer": customer_of(self._tx.context)},
        )
        return credit_profile_from_row(row) if row is not None else None
