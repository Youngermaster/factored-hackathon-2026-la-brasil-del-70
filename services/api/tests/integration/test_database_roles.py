"""Executable proof of deploy/postgres/init/10-roles.sh: the application role can use data, never bypass it."""

from collections.abc import AsyncIterator

import asyncpg
import pytest

from bank_agent_test_support import PostgresInstance


@pytest.fixture
async def owner(postgres: PostgresInstance) -> AsyncIterator[asyncpg.Connection]:
    connection = await asyncpg.connect(
        host=postgres.host,
        port=postgres.port,
        database=postgres.database,
        user=postgres.owner,
        password=postgres.owner_password,
    )
    try:
        yield connection
    finally:
        await connection.close()


@pytest.fixture
async def app_role(postgres: PostgresInstance) -> AsyncIterator[asyncpg.Connection]:
    connection = await asyncpg.connect(
        host=postgres.host,
        port=postgres.port,
        database=postgres.database,
        user=postgres.app_user,
        password=postgres.app_password,
    )
    try:
        yield connection
    finally:
        await connection.close()


async def test_application_role_is_not_privileged(owner: asyncpg.Connection, postgres: PostgresInstance) -> None:
    role = await owner.fetchrow(
        "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication, rolcanlogin "
        "FROM pg_roles WHERE rolname = $1",
        postgres.app_user,
    )

    assert role is not None
    assert dict(role) == {
        "rolsuper": False,
        "rolbypassrls": False,
        "rolcreatedb": False,
        "rolcreaterole": False,
        "rolreplication": False,
        "rolcanlogin": True,
    }


async def test_owner_owns_the_app_schema(owner: asyncpg.Connection, postgres: PostgresInstance) -> None:
    schema_owner = await owner.fetchval("SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname = 'app'")

    assert schema_owner == postgres.owner


async def test_application_role_owns_nothing(owner: asyncpg.Connection, postgres: PostgresInstance) -> None:
    owned = await owner.fetchval(
        "SELECT (SELECT count(*) FROM pg_class WHERE relowner = r.oid)"
        " + (SELECT count(*) FROM pg_namespace WHERE nspowner = r.oid)"
        " + (SELECT count(*) FROM pg_database WHERE datdba = r.oid)"
        " FROM pg_roles r WHERE r.rolname = $1",
        postgres.app_user,
    )

    assert owned == 0


@pytest.mark.parametrize("schema", ["app", "public"])
async def test_application_role_cannot_create_tables(app_role: asyncpg.Connection, schema: str) -> None:
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await app_role.execute(f"CREATE TABLE {schema}.intruder (id integer)")


async def test_application_role_can_use_tables_the_owner_creates(
    owner: asyncpg.Connection, app_role: asyncpg.Connection
) -> None:
    await owner.execute("CREATE TABLE app.role_probe (id integer PRIMARY KEY, note text NOT NULL)")
    try:
        await app_role.execute("INSERT INTO role_probe (id, note) VALUES (1, 'written by the application role')")
        note = await app_role.fetchval("SELECT note FROM role_probe WHERE id = 1")
        await app_role.execute("DELETE FROM role_probe WHERE id = 1")
    finally:
        await owner.execute("DROP TABLE app.role_probe")

    assert note == "written by the application role"


async def test_application_role_cannot_alter_or_drop_owner_tables(
    owner: asyncpg.Connection, app_role: asyncpg.Connection
) -> None:
    await owner.execute("CREATE TABLE app.guarded (id integer)")
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await app_role.execute("DROP TABLE app.guarded")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await app_role.execute("ALTER TABLE app.guarded DISABLE ROW LEVEL SECURITY")
    finally:
        await owner.execute("DROP TABLE app.guarded")
