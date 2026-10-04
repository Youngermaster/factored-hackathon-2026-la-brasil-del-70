"""The operational inspector can read data without changing application isolation or granting writes."""

import importlib.util
import secrets
from pathlib import Path

import asyncpg
import pytest

from bank_agent_contracts import contract_dataset
from bank_agent_postgres_backend import PostgresBackend
from bank_agent_test_support import PostgresInstance

SQL = Path(__file__).resolve().parents[4] / "deploy/data-engineering/datagrip-readonly.sql"
TABLES = ("customers", "products", "transactions", "historical_complaints", "credit_profiles")


async def test_inspector_reads_all_reference_data_without_writes_or_application_rls_changes(
    migrated_postgres: PostgresInstance,
) -> None:
    instance = migrated_postgres
    backend = PostgresBackend(instance)
    await backend.seed(contract_dataset())
    owner = await asyncpg.connect(
        host=instance.host,
        port=instance.port,
        database=instance.database,
        user=instance.owner,
        password=instance.owner_password,
    )
    app = await asyncpg.connect(
        host=instance.host,
        port=instance.port,
        database=instance.database,
        user=instance.app_user,
        password=instance.app_password,
    )
    try:
        await owner.execute(SQL.read_text())
        await owner.execute(SQL.read_text())
        role = await owner.fetchrow(
            "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication, rolcanlogin "
            "FROM pg_roles WHERE rolname = 'bank_datagrip'"
        )
        assert role is not None
        assert not any(role.values())
        spec = importlib.util.spec_from_file_location("datagrip_setup", SQL.with_name("datagrip.py"))
        assert spec is not None
        assert spec.loader is not None
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        password = secrets.token_urlsafe(24)
        verifier = helper.scram_verifier(password, secrets.token_bytes(16)).decode()
        await owner.execute(f"ALTER ROLE bank_datagrip LOGIN PASSWORD '{verifier}'")
        inspector = await asyncpg.connect(
            host=instance.host,
            port=instance.port,
            database=instance.database,
            user="bank_datagrip",
            password=password,
        )
        try:
            assert await inspector.fetchval("SHOW default_transaction_read_only") == "on"
            assert await inspector.fetchval("SHOW statement_timeout") == "30s"
            assert await inspector.fetchval("SELECT count(*) FROM app.customers") > 0
        finally:
            await inspector.close()
        for table in TABLES:
            expected = await owner.fetchval(f"SELECT count(*) FROM app.{table}")  # noqa: S608
            assert expected > 0
            async with owner.transaction():
                await owner.execute("SET LOCAL ROLE bank_datagrip")
                assert await owner.fetchval(f"SELECT count(*) FROM app.{table}") == expected  # noqa: S608
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    async with owner.transaction():
                        await owner.execute(f"DELETE FROM app.{table}")  # noqa: S608
            assert await app.fetchval(f"SELECT count(*) FROM app.{table}") == 0  # noqa: S608
            async with app.transaction():
                await app.execute(
                    "SELECT set_config('app.role', 'customer', true), set_config('app.customer_id', 'CUS-A-0001', true)"
                )
                rows = await app.fetch(f"SELECT DISTINCT customer_id FROM app.{table}")  # noqa: S608
                assert rows
                assert {row["customer_id"] for row in rows} == {"CUS-A-0001"}
        async with owner.transaction():
            await owner.execute("SET LOCAL ROLE bank_datagrip")
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with owner.transaction():
                    await owner.execute("CREATE TABLE app.inspector_write (id int)")
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with owner.transaction():
                    await owner.execute("SELECT count(*) FROM app.dispute_cases")
    finally:
        await owner.execute("RESET ROLE; DROP OWNED BY bank_datagrip; DROP ROLE bank_datagrip;")
        await app.close()
        await owner.close()
        await backend.aclose()
