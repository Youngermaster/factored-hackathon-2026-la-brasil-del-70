"""The data deployment uses the application's merged schema and trusted staff context."""

from datetime import timedelta

import pytest
from sqlalchemy import text

from bank_agent.adapters.persistence.postgres.unit_of_work import PostgresUnitOfWork
from bank_agent.domain.access import AccessContext
from bank_agent.domain.handoff import HandoffOutcomeCode
from bank_agent.domain.identifiers import ConversationId
from bank_agent_builders import T0, conversation, handoff
from bank_agent_contracts import AGENT, CONTEXT_A, contract_dataset
from bank_agent_postgres import app_engine, owner_engine
from bank_agent_postgres_backend import PostgresBackend
from bank_agent_test_support import PostgresInstance


@pytest.mark.parametrize("context", [AGENT, CONTEXT_A])
async def test_staff_context_is_transaction_local_and_reapplied(
    migrated_postgres: PostgresInstance, context: AccessContext
) -> None:
    engine = app_engine(migrated_postgres)
    try:
        async with PostgresUnitOfWork(engine, context) as uow:
            for operation in (None, uow.commit, uow.rollback):
                if operation is not None:
                    await operation()
                assert await uow._open().scalar("SELECT current_setting('app.staff_id', true)") == (
                    context.staff_id or ""
                )
        async with engine.connect() as connection:
            assert not await connection.scalar(text("SELECT current_setting('app.staff_id', true)"))
    finally:
        await engine.dispose()


async def test_resolving_a_claimed_handoff_closes_its_customer_conversation(
    migrated_postgres: PostgresInstance,
) -> None:
    backend = PostgresBackend(migrated_postgres)
    try:
        await backend.seed(contract_dataset())
        async with backend.uow_factory()(CONTEXT_A) as uow:
            await uow.conversations.add(conversation())
            await uow.handoffs.add(handoff())
            await uow.commit()
        async with backend.uow_factory()(AGENT) as uow:
            await uow.handoffs.claim(handoff().handoff_id, at=T0)
            await uow.handoffs.resolve(
                handoff().handoff_id,
                outcome=HandoffOutcomeCode.RESOLVED_BY_AGENT,
                note="Verified completion.",
                at=T0 + timedelta(minutes=1),
            )
            await uow.commit()
        async with backend.uow_factory()(CONTEXT_A) as uow:
            stored = await uow.conversations.get(ConversationId("conv-000001"))
            assert stored is not None
            assert stored.status.value == "closed"
            assert stored.version == 1
            assert stored.updated_at == T0 + timedelta(minutes=1)
    finally:
        await backend.aclose()


async def test_human_messages_have_forced_rls_and_append_only_application_grants(
    migrated_postgres: PostgresInstance,
) -> None:
    engine = owner_engine(migrated_postgres)
    try:
        async with engine.connect() as connection:
            flags = (
                await connection.execute(
                    text(
                        "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                        "WHERE oid = 'app.human_messages'::regclass"
                    )
                )
            ).one()
            assert tuple(flags) == (True, True)
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                allowed = await connection.scalar(
                    text("SELECT has_table_privilege(:role, 'app.human_messages', :privilege)"),
                    {"role": migrated_postgres.app_user, "privilege": privilege},
                )
                assert allowed is (privilege in {"SELECT", "INSERT"})
    finally:
        await engine.dispose()
