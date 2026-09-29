"""Migration 0009 preserves old turns and isolates the new chat and profile rows."""

import secrets

import asyncpg
import pytest
from testcontainers.community.postgres import PostgresContainer

from bank_agent.adapters.persistence.postgres import migrate
from bank_agent_builders import CUSTOMER_A, CUSTOMER_B, T0, conversation
from bank_agent_contracts import CONTEXT_A, contract_dataset
from bank_agent_postgres import (
    APP_USER,
    DATABASE,
    INIT_SCRIPTS,
    OWNER,
    compose_postgres_image,
    owner_engine,
)
from bank_agent_postgres_backend import PostgresBackend
from bank_agent_test_support import PostgresInstance


async def _connect(instance: PostgresInstance) -> asyncpg.Connection:
    return await asyncpg.connect(
        host=instance.host,
        port=instance.port,
        database=instance.database,
        user=instance.app_user,
        password=instance.app_password,
    )


async def test_customer_scoped_profiles_and_ordered_messages(migrated_postgres: PostgresInstance) -> None:
    backend = PostgresBackend(migrated_postgres)
    await backend.seed(contract_dataset())
    async with backend.uow_factory()(CONTEXT_A) as uow:
        await uow.conversations.add(conversation())
        await uow.commit()

    app = await _connect(migrated_postgres)
    try:
        async with app.transaction():
            await app.execute(
                "SELECT set_config('app.role', 'customer', true), set_config('app.customer_id', $1, true)", CUSTOMER_A
            )
            await app.execute(
                "INSERT INTO app.assistant_profiles (customer_id, assistant_name, avatar_key, updated_at) "
                "VALUES ($1, 'Luna', 'luna_1', $2)",
                CUSTOMER_A,
                T0,
            )
            await app.execute(
                "INSERT INTO app.messages "
                "(message_id, conversation_id, customer_id, sequence, sent_at, role, text, is_simulated) "
                "VALUES ('msg-1', 'conv-000001', $1, 1, $2, 'mock_human', 'Demo response', true)",
                CUSTOMER_A,
                T0,
            )
            assert await app.fetchval("SELECT assistant_name FROM app.assistant_profiles") == "Luna"
            assert await app.fetchval("SELECT role FROM app.messages WHERE sequence = 1") == "mock_human"

        async with app.transaction():
            await app.execute(
                "SELECT set_config('app.role', 'customer', true), set_config('app.customer_id', $1, true)", CUSTOMER_B
            )
            assert await app.fetchval("SELECT count(*) FROM app.assistant_profiles") == 0
            assert await app.fetchval("SELECT count(*) FROM app.messages") == 0
            with pytest.raises(asyncpg.ForeignKeyViolationError):
                await app.execute(
                    "INSERT INTO app.messages "
                    "(message_id, conversation_id, customer_id, sequence, sent_at, role, text) "
                    "VALUES ('msg-foreign', 'conv-000001', $1, 2, $2, 'user', 'foreign')",
                    CUSTOMER_B,
                    T0,
                )

        async with app.transaction():
            await app.execute(
                "SELECT set_config('app.role', 'customer', true), set_config('app.customer_id', $1, true)", CUSTOMER_A
            )
            assert await app.fetchval("SELECT assistant_name FROM app.assistant_profiles") == "Luna"
            await app.execute(
                "UPDATE app.assistant_profiles SET assistant_name = 'Sol', updated_at = $1 WHERE customer_id = $2",
                T0,
                CUSTOMER_A,
            )
            assert await app.fetchval("SELECT assistant_name FROM app.assistant_profiles") == "Sol"
            assert await app.fetchval("SELECT count(*) FROM app.messages") == 1

        async with app.transaction():
            await app.execute(
                "SELECT set_config('app.role', 'customer', true), set_config('app.customer_id', $1, true)", CUSTOMER_A
            )
            with pytest.raises(asyncpg.CheckViolationError, match="messages_mock_is_simulated"):
                await app.execute(
                    "INSERT INTO app.messages "
                    "(message_id, conversation_id, customer_id, sequence, sent_at, role, text) "
                    "VALUES ('msg-invalid', 'conv-000001', $1, 2, $2, 'mock_human', 'unlabeled')",
                    CUSTOMER_A,
                    T0,
                )
    finally:
        await app.close()
        await backend.aclose()


async def test_existing_turn_is_backfilled_when_upgrading_from_0008() -> None:
    owner_password, app_password = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    container = (
        PostgresContainer(
            compose_postgres_image(), username=OWNER, password=owner_password, dbname=DATABASE, driver=None
        )
        .with_env("POSTGRES_APP_USER", APP_USER)
        .with_env("POSTGRES_APP_PASSWORD", app_password)
        .with_volume_mapping(str(INIT_SCRIPTS), "/docker-entrypoint-initdb.d", "ro")
    )
    with container:
        instance = PostgresInstance(
            host=container.get_container_host_ip(),
            port=int(container.get_exposed_port(5432)),
            database=DATABASE,
            owner=OWNER,
            owner_password=owner_password,
            app_user=APP_USER,
            app_password=app_password,
        )
        engine = owner_engine(instance)
        try:
            await migrate.upgrade(engine, app_role=APP_USER, target="0008")
            owner = await asyncpg.connect(
                host=instance.host, port=instance.port, database=DATABASE, user=OWNER, password=owner_password
            )
            try:
                await owner.execute(
                    "INSERT INTO app.customers (customer_id, country, segment, status, first_name) "
                    "VALUES ($1, 'MX', 'basic', 'active', 'Test')",
                    CUSTOMER_A,
                )
                await owner.execute(
                    "INSERT INTO app.conversations "
                    "(conversation_id, customer_id, lineage_id, status, created_at, version, document) "
                    "VALUES ('conv-000001', $1, 'lineage-1', 'active', $2, 0, "
                    '\'{"conversation_id":"conv-000001","customer_id":"CUS-A-0001","status":"active","version":0}\'::jsonb)',
                    CUSTOMER_A,
                    T0,
                )
                await owner.execute(
                    "INSERT INTO app.turns "
                    "(turn_id, conversation_id, customer_id, sequence, received_at, document) "
                    "VALUES ('turn-legacy', 'conv-000001', $1, 1, $2, "
                    '\'{"turn_id":"turn-legacy","conversation_id":"conv-000001","sequence":1,'
                    '"customer_text":"Hola","response":{"text":"Buen día"}}\'::jsonb)',
                    CUSTOMER_A,
                    T0,
                )
            finally:
                await owner.close()

            await migrate.upgrade(engine, app_role=APP_USER)
            await migrate.upgrade(engine, app_role=APP_USER)
            owner = await asyncpg.connect(
                host=instance.host, port=instance.port, database=DATABASE, user=OWNER, password=owner_password
            )
            try:
                rows = await owner.fetch(
                    "SELECT sequence, role, text, turn_id FROM app.messages WHERE conversation_id = 'conv-000001' "
                    "ORDER BY sequence"
                )
                assert [(row["sequence"], row["role"], row["text"], row["turn_id"]) for row in rows] == [
                    (1, "user", "Hola", "turn-legacy"),
                    (2, "assistant", "Buen día", "turn-legacy"),
                ]
                assert await migrate.current_revision(engine) == migrate.head_revision()
            finally:
                await owner.close()
        finally:
            await engine.dispose()
