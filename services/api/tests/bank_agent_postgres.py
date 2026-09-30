"""PostgreSQL for integration and contract tests: one migrated container per test session.

The container uses the image pinned in docker-compose.yml and the repository role script. Passwords are
generated at runtime and exist only in this process and the container; nothing is read from or written to .env.
The root ``conftest.py`` registers the ``postgres`` and ``migrated_postgres`` fixtures from this module, so the
service, contract, and data platform suites share one container.
"""

import asyncio
import re
import secrets
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from testcontainers.community.postgres import PostgresContainer

from bank_agent.adapters.persistence.postgres import migrate
from bank_agent.adapters.persistence.postgres.database import create_engine, database_url
from bank_agent_test_support import PostgresInstance

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
INIT_SCRIPTS = REPOSITORY_ROOT / "deploy" / "postgres" / "init"
OWNER = "bank_owner"
APP_USER = "bank_app"
DATABASE = "bank_agent"
RUNTIME_TABLES = (
    "rate_limit_windows",
    "llm_budget",
    "audit_events",
    "execution_records",
    "trust_events",
    "handoffs",
    "messages",
    "turns",
    "conversations",
    "assistant_profiles",
    "otp_challenges",
    "sessions",
    "action_idempotency",
    "credit_applications",
    "dispute_cases",
    "credit_profiles",
    "historical_complaints",
    "transactions",
    "products",
    "identity_directory",
    "staff_members",
    "customers",
)


def compose_postgres_image() -> str:
    """The PostgreSQL image pinned in docker-compose.yml, so tests and the dev stack never drift."""
    compose = (REPOSITORY_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    match = re.search(r"^\s+image:\s+(postgres:\S+)\s*$", compose, flags=re.MULTILINE)
    if match is None:
        raise RuntimeError("docker-compose.yml does not pin a postgres image")
    return match.group(1)


def owner_engine(instance: PostgresInstance) -> AsyncEngine:
    url = database_url(
        user=instance.owner,
        password=instance.owner_password,
        host=instance.host,
        port=instance.port,
        database=instance.database,
    )
    return create_engine(url, pooled=False)


def app_engine(instance: PostgresInstance) -> AsyncEngine:
    url = database_url(
        user=instance.app_user,
        password=instance.app_password,
        host=instance.host,
        port=instance.port,
        database=instance.database,
    )
    return create_engine(url, pooled=False)


async def _migrate(instance: PostgresInstance) -> None:
    engine = owner_engine(instance)
    try:
        await migrate.upgrade(engine, app_role=instance.app_user)
    finally:
        await engine.dispose()


async def reset_database(instance: PostgresInstance) -> None:
    """Empty every table as the owner. Replica mode skips the append-only truncate triggers (tests only)."""
    engine = owner_engine(instance)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SET LOCAL session_replication_role = replica"))
            await connection.execute(text(f"TRUNCATE {', '.join('app.' + t for t in RUNTIME_TABLES)}"))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def postgres() -> Iterator[PostgresInstance]:
    owner_password = secrets.token_urlsafe(24)
    app_password = secrets.token_urlsafe(24)
    container = (
        PostgresContainer(
            compose_postgres_image(), username=OWNER, password=owner_password, dbname=DATABASE, driver=None
        )
        .with_env("POSTGRES_APP_USER", APP_USER)
        .with_env("POSTGRES_APP_PASSWORD", app_password)
        .with_volume_mapping(str(INIT_SCRIPTS), "/docker-entrypoint-initdb.d", "ro")
    )
    with container:
        yield PostgresInstance(
            host=container.get_container_host_ip(),
            port=int(container.get_exposed_port(5432)),
            database=DATABASE,
            owner=OWNER,
            owner_password=owner_password,
            app_user=APP_USER,
            app_password=app_password,
        )


@pytest.fixture(scope="session")
def migrated_postgres(postgres: PostgresInstance) -> PostgresInstance:
    """The session database with every migration applied.

    The migration runs on a thread of its own, because this fixture may be requested from inside a running
    event loop (an async contract fixture calling ``getfixturevalue``).
    """
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(asyncio.run, _migrate(postgres)).result()
    return postgres
