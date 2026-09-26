import httpx
import pytest
import structlog
from fastapi import APIRouter

from bank_agent.api.app import create_app
from bank_agent_test_support import FakeProvider, api_config


def _client() -> httpx.AsyncClient:
    app = create_app(FakeProvider(), api_config())
    router = APIRouter()

    @router.get("/echo-context")
    async def echo_context() -> dict[str, object]:
        return dict(structlog.contextvars.get_contextvars())

    app.include_router(router)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


async def test_generates_a_request_id_when_none_is_sent() -> None:
    async with _client() as client:
        first = await client.get("/health/live")
        second = await client.get("/health/live")

    assert first.headers["X-Request-ID"] == "req-00000001"
    assert second.headers["X-Request-ID"] == "req-00000002"


async def test_echoes_a_valid_inbound_request_id() -> None:
    async with _client() as client:
        response = await client.get("/health/live", headers={"X-Request-ID": "client-abc-12345"})

    assert response.headers["X-Request-ID"] == "client-abc-12345"


@pytest.mark.parametrize("inbound", ["short", "has spaces in it", "x" * 65, "semi;colon-12345", "line\\nbreak-123"])
async def test_replaces_a_malformed_inbound_request_id(inbound: str) -> None:
    async with _client() as client:
        response = await client.get("/health/live", headers={"X-Request-ID": inbound})

    assert response.headers["X-Request-ID"] == "req-00000001"


async def test_binds_the_request_id_to_the_log_context_for_the_request_only() -> None:
    async with _client() as client:
        response = await client.get("/echo-context", headers={"X-Request-ID": "client-abc-12345"})

    assert response.json() == {"request_id": "client-abc-12345"}
    assert "request_id" not in structlog.contextvars.get_contextvars()
