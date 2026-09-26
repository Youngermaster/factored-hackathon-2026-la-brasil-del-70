import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest

from bank_agent.api.app import create_app
from bank_agent.asgi import api_config_from
from bank_agent.bootstrap.container import Container
from bank_agent.bootstrap.settings import load_settings
from bank_agent_test_support import PostgresInstance


@asynccontextmanager
async def open_client() -> AsyncIterator[httpx.AsyncClient]:
    """The real application, wired from the current environment, with its lifespan running."""
    settings = load_settings(env_file=None)
    app = create_app(Container(settings), api_config_from(settings))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client,
    ):
        yield client


def _closed_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
    return port


@pytest.mark.usefixtures("database_environment")
async def test_ready_reports_the_database_ok_as_the_application_role() -> None:
    async with open_client() as client:
        response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok"}}


@pytest.mark.usefixtures("database_environment")
async def test_live_reports_live_with_a_database_configured() -> None:
    async with open_client() as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "live"}


async def test_ready_returns_503_when_the_database_is_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_PORT", str(_closed_local_port()))
    monkeypatch.setenv("POSTGRES_APP_PASSWORD", "unreachable-database-password")

    async with open_client() as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "checks": {"database": "unavailable"}}
    assert "unreachable-database-password" not in response.text


async def test_ready_returns_503_when_the_application_password_is_wrong(
    database_environment: PostgresInstance, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POSTGRES_APP_PASSWORD", "not-the-application-password")

    async with open_client() as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "checks": {"database": "unavailable"}}
