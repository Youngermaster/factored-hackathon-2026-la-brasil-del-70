"""Idempotent loading of demo data into PostgreSQL, as the owner role with ``app.role = 'seed'``.

Reference tables (customers, products, transactions, complaints, credit profiles, the identity directory, and
staff) are upserted on their primary keys, so a rerun leaves the same rows, and a product's status returns to the
source value (a demo reset). Seeded dispute cases and credit applications are inserted only when missing.
Tables the service writes at run time (sessions, conversations, records, handoffs, audit) are never touched.
When a source selects a different customer for a persona, its previous assignment is cleared before loading.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from bank_agent.adapters.persistence.postgres.database import DatabaseRole, open_transaction
from bank_agent.adapters.persistence.postgres.mappers.accounts import (
    customer_to_row,
    product_to_row,
    transaction_to_row,
)
from bank_agent.adapters.persistence.postgres.mappers.cases import application_to_row, case_to_row
from bank_agent.adapters.persistence.postgres.mappers.history import complaint_to_row, credit_profile_to_row
from bank_agent.domain.complaint import HistoricalComplaint
from bank_agent.domain.credit import CreditApplicationIntake, CreditProfile
from bank_agent.domain.customer import Customer
from bank_agent.domain.dispute import DisputeCase
from bank_agent.domain.product import Product
from bank_agent.domain.transaction import Transaction


@dataclass(frozen=True)
class IdentityEntry:
    """How a customer can identify: a persona id and keyed digests of the document and phone. Never raw values."""

    customer_id: str
    persona_id: str | None
    document_lookup: str
    phone_last4_lookup: str


@dataclass(frozen=True)
class StaffEntry:
    staff_id: str
    role: str
    persona_id: str
    display_name: str


@dataclass(frozen=True)
class SeedBundle:
    customers: Sequence[Customer] = ()
    products: Sequence[Product] = ()
    transactions: Sequence[Transaction] = ()
    complaints: Sequence[HistoricalComplaint] = ()
    credit_profiles: Sequence[CreditProfile] = ()
    identities: Sequence[IdentityEntry] = ()
    staff: Sequence[StaffEntry] = ()
    cases: Sequence[DisputeCase] = field(default=())
    credit_applications: Sequence[CreditApplicationIntake] = field(default=())


@dataclass(frozen=True)
class SeedCounts:
    """Rows written per table (inserted or updated)."""

    counts: dict[str, int]


def _upsert(table: str, columns: Sequence[str], key: Sequence[str], *, update: bool, casts: dict[str, str]) -> str:
    """An INSERT for one of the fixed seed tables. Table and column names come only from this module."""
    values = ", ".join(f"CAST(:{name} AS {casts[name]})" if name in casts else f":{name}" for name in columns)
    conflict = f"ON CONFLICT ({', '.join(key)}) "
    changed = [name for name in columns if name not in key]
    assignments = ", ".join(f"{name} = EXCLUDED.{name}" for name in changed)
    action = f"DO UPDATE SET {assignments}" if update else "DO NOTHING"  # nosec B608
    return f"INSERT INTO app.{table} ({', '.join(columns)}) VALUES ({values}) {conflict}{action}"  # noqa: S608  # nosec B608 (fixed names)


async def _write(
    connection: AsyncConnection,
    table: str,
    rows: Sequence[dict[str, Any]],
    key: Sequence[str],
    *,
    update: bool = True,
    casts: dict[str, str] | None = None,
) -> int:
    if not rows:
        return 0
    statement = _upsert(table, list(rows[0]), key, update=update, casts=casts or {})
    await connection.execute(text(statement), list(rows))
    return len(rows)


class PostgresSeeder:
    """Loads a ``SeedBundle`` in one transaction over an owner-role engine."""

    def __init__(self, owner_engine: AsyncEngine) -> None:
        self._engine = owner_engine

    async def load(self, bundle: SeedBundle) -> SeedCounts:
        counts: dict[str, int] = {}
        document = {"document": "jsonb"}
        async with open_transaction(self._engine, DatabaseRole.SEED) as connection:
            counts["customers"] = await _write(
                connection, "customers", [customer_to_row(item) for item in bundle.customers], ["customer_id"]
            )
            counts["staff_members"] = await _write(
                connection, "staff_members", [vars(item) for item in bundle.staff], ["staff_id"]
            )
            reassigned = [vars(item) for item in bundle.identities if item.persona_id is not None]
            if reassigned:
                await connection.execute(
                    text(
                        "UPDATE app.identity_directory SET persona_id = NULL "
                        "WHERE persona_id = :persona_id AND customer_id <> :customer_id"
                    ),
                    reassigned,
                )
            counts["identity_directory"] = await _write(
                connection, "identity_directory", [vars(item) for item in bundle.identities], ["customer_id"]
            )
            counts["products"] = await _write(
                connection, "products", [product_to_row(item) for item in bundle.products], ["product_id"]
            )
            counts["transactions"] = await _write(
                connection,
                "transactions",
                [transaction_to_row(item) for item in bundle.transactions],
                ["transaction_id"],
            )
            counts["historical_complaints"] = await _write(
                connection,
                "historical_complaints",
                [complaint_to_row(item) for item in bundle.complaints],
                ["complaint_id"],
            )
            counts["credit_profiles"] = await _write(
                connection,
                "credit_profiles",
                [credit_profile_to_row(item) for item in bundle.credit_profiles],
                ["customer_id"],
            )
            counts["dispute_cases"] = await _write(
                connection,
                "dispute_cases",
                [case_to_row(item) for item in bundle.cases],
                ["case_id"],
                update=False,
                casts=document,
            )
            counts["credit_applications"] = await _write(
                connection,
                "credit_applications",
                [application_to_row(item) for item in bundle.credit_applications],
                ["application_id"],
                update=False,
                casts=document,
            )
        return SeedCounts(counts=counts)
