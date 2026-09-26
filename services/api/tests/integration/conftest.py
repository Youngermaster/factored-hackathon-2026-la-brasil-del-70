"""PostgreSQL for integration tests.

One throwaway container per test session, from the same image as docker-compose.yml, initialized with the
repository role script. Both passwords are generated at runtime and exist only in this process and the
container; nothing is read from or written to .env.
"""

import re
import secrets
from collections.abc import Iterator
from pathlib import Path

import pytest
from testcontainers.community.postgres import PostgresContainer

from bank_agent_test_support import PostgresInstance

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
INIT_SCRIPTS = REPOSITORY_ROOT / "deploy" / "postgres" / "init"
OWNER = "bank_owner"
APP_USER = "bank_app"
DATABASE = "bank_agent"


def compose_postgres_image() -> str:
    """The PostgreSQL image pinned in docker-compose.yml, so tests and the dev stack never drift."""
    compose = (REPOSITORY_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    match = re.search(r"^\s+image:\s+(postgres:\S+)\s*$", compose, flags=re.MULTILINE)
    if match is None:
        raise RuntimeError("docker-compose.yml does not pin a postgres image")
    return match.group(1)


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


@pytest.fixture
def database_environment(postgres: PostgresInstance, monkeypatch: pytest.MonkeyPatch) -> PostgresInstance:
    """Point the settings at the test database, connecting as the application role."""
    monkeypatch.setenv("POSTGRES_HOST", postgres.host)
    monkeypatch.setenv("POSTGRES_PORT", str(postgres.port))
    monkeypatch.setenv("POSTGRES_DB", postgres.database)
    monkeypatch.setenv("POSTGRES_APP_USER", postgres.app_user)
    monkeypatch.setenv("POSTGRES_APP_PASSWORD", postgres.app_password)
    return postgres
