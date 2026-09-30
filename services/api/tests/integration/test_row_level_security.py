"""Row-level security as defense in depth: raw SQL as the application role, below every repository."""

from collections.abc import AsyncIterator

import asyncpg
import pytest

from bank_agent.domain.credit import ApplicationStatus
from bank_agent.domain.eligibility import CreditReview
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.handoff import EscalationReason
from bank_agent.domain.identifiers import ApplicationId, HandoffId
from bank_agent_builders import T0, eligibility_assessment, handoff, handoff_v1_1
from bank_agent_contracts import CONTEXT_A, contract_dataset
from bank_agent_postgres_backend import PostgresBackend
from bank_agent_test_support import PostgresInstance

CUSTOMER_TABLES = (
    "customers",
    "products",
    "transactions",
    "historical_complaints",
    "credit_profiles",
    "dispute_cases",
    "credit_applications",
)
AGENT_HIDDEN_TABLES = tuple(table for table in CUSTOMER_TABLES if table != "credit_applications")
"""A submitted intake is a review item of its own, so agents read reviewable credit applications (0010)."""


@pytest.fixture
async def seeded(migrated_postgres: PostgresInstance) -> AsyncIterator[PostgresInstance]:
    backend = PostgresBackend(migrated_postgres)
    await backend.seed(contract_dataset())
    yield migrated_postgres
    await backend.aclose()


async def _connect(instance: PostgresInstance, *, owner: bool = False) -> asyncpg.Connection:
    return await asyncpg.connect(
        host=instance.host,
        port=instance.port,
        database=instance.database,
        user=instance.owner if owner else instance.app_user,
        password=instance.owner_password if owner else instance.app_password,
    )


async def _count(connection: asyncpg.Connection, table: str, role: str = "", customer: str = "") -> int:
    async with connection.transaction():
        await connection.execute(
            "SELECT set_config('app.role', $1, true), set_config('app.customer_id', $2, true)", role, customer
        )
        return int(await connection.fetchval(f"SELECT count(*) FROM app.{table}"))  # noqa: S608


@pytest.mark.parametrize("table", CUSTOMER_TABLES)
async def test_raw_sql_without_a_context_returns_no_rows(seeded: PostgresInstance, table: str) -> None:
    app, owner = await _connect(seeded), await _connect(seeded, owner=True)
    try:
        assert await _count(owner, table) > 0
        assert await _count(app, table) == 0
    finally:
        await app.close()
        await owner.close()


@pytest.mark.parametrize("table", CUSTOMER_TABLES)
async def test_a_customer_context_sees_only_that_customers_rows(seeded: PostgresInstance, table: str) -> None:
    app = await _connect(seeded)
    try:
        async with app.transaction():
            await app.execute(
                "SELECT set_config('app.role', 'customer', true), set_config('app.customer_id', $1, true)", "CUS-A-0001"
            )
            owners = await app.fetch(f"SELECT DISTINCT customer_id FROM app.{table}")  # noqa: S608
    finally:
        await app.close()
    assert {row["customer_id"] for row in owners} <= {"CUS-A-0001"}


async def test_a_customer_role_without_a_customer_sees_nothing(seeded: PostgresInstance) -> None:
    app = await _connect(seeded)
    try:
        assert await _count(app, "products", role="customer") == 0
        assert await _count(app, "products", role="customer", customer="CUS-Z-9999") == 0
    finally:
        await app.close()


@pytest.mark.parametrize("table", [*AGENT_HIDDEN_TABLES, "execution_records", "conversations"])
async def test_the_agent_role_reads_no_customer_data(seeded: PostgresInstance, table: str) -> None:
    app = await _connect(seeded)
    try:
        assert await _count(app, table, role="agent") == 0
    finally:
        await app.close()


@pytest.mark.parametrize("table", [*CUSTOMER_TABLES, "execution_records", "conversations"])
async def test_the_evaluator_and_identity_roles_read_no_customer_data(seeded: PostgresInstance, table: str) -> None:
    app = await _connect(seeded)
    try:
        assert await _count(app, table, role="evaluator") == 0
        assert await _count(app, table, role="identity") == 0
    finally:
        await app.close()


async def test_the_agent_reads_reviewable_applications_and_referenced_ones(
    migrated_postgres: PostgresInstance,
) -> None:
    backend = PostgresBackend(migrated_postgres)
    await backend.seed(contract_dataset())
    app = await _connect(migrated_postgres)
    existing = ApplicationId("app-000001")
    try:
        assert await _count(app, "credit_applications", role="agent") == 1
        for status in ("withdrawn", "submitted"):  # agents only move intakes into review or close them (0013)
            async with app.transaction():
                await app.execute("SELECT set_config('app.role', 'agent', true)")
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await app.execute(f"UPDATE app.credit_applications SET status = '{status}'")  # noqa: S608
        async with app.transaction():
            await app.execute("SELECT set_config('app.role', 'customer', true)")
            await app.execute("SELECT set_config('app.customer_id', 'CUS-B-0002', true)")
            assert await app.execute("UPDATE app.credit_applications SET version = version") == "UPDATE 0"
        async with backend.uow_factory()(CONTEXT_A) as uow:
            await uow.credit_applications.transition(
                existing, ApplicationStatus.WITHDRAWN, expected_version=0, at=T0, reason_code="customer_request"
            )
            await uow.commit()
        assert await _count(app, "credit_applications", role="agent") == 0
        review = CreditReview.from_assessment(
            eligibility_assessment(outcome="review_required", review_reasons=["borderline_risk_interval"]),
            application_ref=existing,
        )
        async with backend.uow_factory()(CONTEXT_A) as uow:
            await uow.handoffs.add(
                handoff_v1_1(
                    handoff_id=HandoffId("ho-credit-01"),
                    case_ref=None,
                    actions_taken=[],
                    escalation_reason=EscalationReason(
                        code=EscalationReasonCode.CREDIT_REVIEW_REQUIRED, detail="Borderline indicative result."
                    ),
                    credit_review=review,
                )
            )
            await uow.commit()
        assert await _count(app, "credit_applications", role="agent") == 1
    finally:
        await app.close()
        await backend.aclose()


async def test_the_agent_reads_a_case_only_once_a_handoff_references_it(migrated_postgres: PostgresInstance) -> None:
    backend = PostgresBackend(migrated_postgres)
    await backend.seed(contract_dataset())
    app = await _connect(migrated_postgres)
    try:
        assert await _count(app, "dispute_cases", role="agent") == 0
        async with backend.uow_factory()(CONTEXT_A) as uow:
            await uow.handoffs.add(handoff(case_ref="case-000001"))
            await uow.commit()
        assert await _count(app, "dispute_cases", role="agent") == 1
        assert await _count(app, "handoffs", role="agent") == 1
        assert await _count(app, "credit_applications", role="agent") == 1
    finally:
        await app.close()
        await backend.aclose()


async def test_the_context_never_outlives_its_transaction(seeded: PostgresInstance) -> None:
    app = await _connect(seeded)
    try:
        assert await _count(app, "products", role="customer", customer="CUS-A-0001") == 3
        assert int(await app.fetchval("SELECT count(*) FROM app.products")) == 0
    finally:
        await app.close()


async def test_the_application_role_cannot_write_reference_data(seeded: PostgresInstance) -> None:
    app = await _connect(seeded)
    try:
        for statement in (
            "UPDATE app.customers SET first_name = 'X'",
            "UPDATE app.products SET currency = 'USD'",
            "DELETE FROM app.transactions",
            "INSERT INTO app.credit_profiles (customer_id, as_of) VALUES ('CUS-A-0001', '2026-01-01')",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await app.execute(statement)
    finally:
        await app.close()
