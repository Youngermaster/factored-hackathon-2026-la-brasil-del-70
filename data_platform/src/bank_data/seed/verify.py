"""Read-only reconciliation of the deterministic gold seed against PostgreSQL.

Checks the complete selected customer slice, not merely the number of rows the latest upsert attempted.
Only aggregate counts are returned; no customer data or identity digests appear in errors or output.
"""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from bank_agent.adapters.persistence.postgres import migrate
from bank_agent.adapters.persistence.postgres.database import DatabaseRole, open_transaction
from bank_agent.adapters.persistence.postgres.seed import SeedBundle
from bank_data.errors import SeedVerificationError
from bank_data.seed.selection import Selection

_SCOPED_TABLES = (
    ("customers", "customer_id"),
    ("products", "product_id"),
    ("transactions", "transaction_id"),
    ("historical_complaints", "complaint_id"),
    ("credit_profiles", "customer_id"),
)


@dataclass(frozen=True)
class VerificationReport:
    revision: str
    counts: dict[str, int]
    personas: int


def _expected_ids(bundle: SeedBundle) -> dict[str, set[str]]:
    return {
        "customers": {str(item.customer_id) for item in bundle.customers},
        "products": {str(item.product_id) for item in bundle.products},
        "transactions": {str(item.transaction_id) for item in bundle.transactions},
        "historical_complaints": {str(item.complaint_id) for item in bundle.complaints},
        "credit_profiles": {str(item.customer_id) for item in bundle.credit_profiles},
        "identity_directory": {item.customer_id for item in bundle.identities},
        "staff_members": {item.staff_id for item in bundle.staff},
        "dispute_cases": {str(item.case_id) for item in bundle.cases},
        "credit_applications": {str(item.application_id) for item in bundle.credit_applications},
    }


def _assert_same(table: str, expected: set[str], actual: set[str]) -> None:
    if expected != actual:
        raise SeedVerificationError(
            f"{table}: expected {len(expected)} selected rows, found {len(actual)} "
            f"({len(expected - actual)} missing, {len(actual - expected)} extra)"
        )


async def _ids(connection: AsyncConnection, table: str, key: str, customer_ids: list[str]) -> set[str]:
    # Names come only from the fixed table list above, never from user input.
    result = await connection.execute(
        text(f"SELECT {key} FROM app.{table} WHERE customer_id = ANY(CAST(:ids AS text[]))"),  # noqa: S608  # nosec B608
        {"ids": customer_ids},
    )
    return {str(row[0]) for row in result}


async def verify_bundle(owner_engine: AsyncEngine, selection: Selection, bundle: SeedBundle) -> VerificationReport:
    """Require schema head, exact selected reference rows, persona lookups and seeded demo records."""
    revision = await migrate.current_revision(owner_engine)
    head = migrate.head_revision()
    if revision != head:
        raise SeedVerificationError(f"PostgreSQL revision is {revision or 'base'}; expected {head}")

    expected = _expected_ids(bundle)
    selected = selection.customers
    _assert_same("customers", set(selected), expected["customers"])
    _assert_same("identity_directory", set(selected), expected["identity_directory"])

    async with open_transaction(owner_engine, DatabaseRole.SEED) as connection:
        for table, key in _SCOPED_TABLES:
            _assert_same(table, expected[table], await _ids(connection, table, key, selected))

        identities = await connection.execute(
            text(
                "SELECT customer_id, persona_id, document_lookup, phone_last4_lookup "
                "FROM app.identity_directory WHERE customer_id = ANY(CAST(:ids AS text[]))"
            ),
            {"ids": selected},
        )
        actual_identity = {str(row.customer_id): tuple(row[1:]) for row in identities}
        expected_identity = {
            item.customer_id: (item.persona_id, item.document_lookup, item.phone_last4_lookup)
            for item in bundle.identities
        }
        _assert_same("identity_directory", expected["identity_directory"], set(actual_identity))
        if actual_identity != expected_identity:
            raise SeedVerificationError("identity_directory: persona or keyed lookup differs from gold selection")

        staff = await connection.execute(
            text("SELECT staff_id, role, persona_id FROM app.staff_members WHERE staff_id = ANY(CAST(:ids AS text[]))"),
            {"ids": list(expected["staff_members"])},
        )
        actual_staff = {str(row.staff_id): (row.role, row.persona_id) for row in staff}
        wanted_staff = {item.staff_id: (item.role, item.persona_id) for item in bundle.staff}
        if actual_staff != wanted_staff:
            raise SeedVerificationError("staff_members: missing or changed demo staff")

        for table, key in (("dispute_cases", "case_id"), ("credit_applications", "application_id")):
            result = await connection.execute(
                text(
                    f"SELECT {key} FROM app.{table} WHERE customer_id = ANY(CAST(:ids AS text[])) "  # noqa: S608  # nosec B608
                    f"AND {key} LIKE :seed_prefix"
                ),
                {"ids": selected, "seed_prefix": "case-seed-%" if table == "dispute_cases" else "app-seed-%"},
            )
            _assert_same(table, expected[table], {str(row[0]) for row in result})

    return VerificationReport(
        revision=head,
        counts={table: len(ids) for table, ids in expected.items()},
        personas=len(selection.personas),
    )
