"""Append-only tables, the credit application status constraint, and the isolated evaluation schema."""

from collections.abc import AsyncIterator
from datetime import timedelta

import asyncpg
import pytest

from bank_agent.adapters.persistence.postgres import migrate
from bank_agent.domain.audit import AuditEvent, AuditOutcome
from bank_agent_builders import T0, execution_record, handoff
from bank_agent_contracts import CONTEXT_A, contract_dataset
from bank_agent_postgres import owner_engine
from bank_agent_postgres_backend import PostgresBackend
from bank_agent_test_support import PostgresInstance

APPEND_ONLY = ("execution_records", "audit_events")


@pytest.fixture
async def with_history(migrated_postgres: PostgresInstance) -> AsyncIterator[PostgresInstance]:
    backend = PostgresBackend(migrated_postgres)
    await backend.seed(contract_dataset())
    async with backend.uow_factory()(CONTEXT_A) as uow:
        await uow.execution_records.append(execution_record("turn-000001"))
        await uow.audit.append(
            AuditEvent(
                event_id="aud-000001",
                occurred_at=T0 + timedelta(minutes=1),
                action="create_dispute_case",
                outcome=AuditOutcome.SUCCESS,
            )
        )
        await uow.commit()
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


@pytest.mark.parametrize("table", APPEND_ONLY)
async def test_the_application_role_cannot_update_or_delete_append_only_rows(
    with_history: PostgresInstance, table: str
) -> None:
    app = await _connect(with_history)
    try:
        statements = (f"UPDATE app.{table} SET document = document", f"DELETE FROM app.{table}")  # noqa: S608
        for statement in statements:
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await app.execute(statement)
    finally:
        await app.close()


@pytest.mark.parametrize("table", APPEND_ONLY)
async def test_even_the_owner_cannot_update_delete_or_truncate_append_only_rows(
    with_history: PostgresInstance, table: str
) -> None:
    owner = await _connect(with_history, owner=True)
    try:
        assert int(await owner.fetchval(f"SELECT count(*) FROM app.{table}")) == 1  # noqa: S608
        for statement in (
            f"UPDATE app.{table} SET document = document",  # noqa: S608
            f"DELETE FROM app.{table}",  # noqa: S608
            f"TRUNCATE app.{table}",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError, match="append-only"):
                await owner.execute(statement)
        assert int(await owner.fetchval(f"SELECT count(*) FROM app.{table}")) == 1  # noqa: S608
    finally:
        await owner.close()


async def test_the_handoff_document_never_changes_but_its_lifecycle_does(
    migrated_postgres: PostgresInstance,
) -> None:
    backend = PostgresBackend(migrated_postgres)
    await backend.seed(contract_dataset())
    async with backend.uow_factory()(CONTEXT_A) as uow:
        await uow.handoffs.add(handoff())
        await uow.commit()
    owner = await _connect(migrated_postgres, owner=True)
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError, match="never changes"):
            await owner.execute('UPDATE app.handoffs SET document = document || \'{"priority": "low"}\'')
        await owner.execute("UPDATE app.handoffs SET sla_due = sla_due")
    finally:
        await owner.close()
        await backend.aclose()


@pytest.mark.parametrize("status", ["approved", "declined", "rejected", "SUBMITTED"])
async def test_credit_applications_accept_only_the_review_lifecycle(
    with_history: PostgresInstance, status: str
) -> None:
    owner = await _connect(with_history, owner=True)
    try:
        with pytest.raises(asyncpg.CheckViolationError, match="credit_applications_status_lifecycle"):
            await owner.execute(
                "UPDATE app.credit_applications SET status = $1, "
                "document = jsonb_set(document, '{status}', to_jsonb($1::text))",
                status,
            )
    finally:
        await owner.close()


async def test_the_evaluation_schema_is_isolated(migrated_postgres: PostgresInstance) -> None:
    app, owner = await _connect(migrated_postgres), await _connect(migrated_postgres, owner=True)
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await app.fetchval("SELECT count(*) FROM eval.evaluation_runs")
        async with owner.transaction():
            await owner.execute("SET LOCAL ROLE bank_evaluator")
            assert await owner.fetchval("SELECT count(*) FROM eval.evaluation_runs") == 0
            assert await owner.fetchval("SELECT count(*) FROM app.execution_records") >= 0
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await owner.fetchval("SELECT count(*) FROM app.customers")
    finally:
        await app.close()
        await owner.close()


async def test_migrations_are_at_head_and_idempotent(migrated_postgres: PostgresInstance) -> None:
    engine = owner_engine(migrated_postgres)
    try:
        await migrate.upgrade(engine, app_role=migrated_postgres.app_user)
        assert await migrate.current_revision(engine) == migrate.head_revision()
    finally:
        await engine.dispose()
