"""Security headers on every response class, the body limit, CORS, and the service-unavailable path."""

from collections.abc import AsyncIterator

import httpx
import pytest

from bank_agent.api.app import create_app
from bank_agent.api.config import SecurityConfig
from bank_agent.api.middleware import API_CSP, DOCS_CSP, HSTS
from bank_agent_test_support import FakeProvider, api_config

BASE_HEADERS = {
    "content-security-policy": API_CSP,
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
    "cross-origin-opener-policy": "same-origin",
    "cross-origin-resource-policy": "same-origin",
}


def _client(security: SecurityConfig | None = None, *, expose_docs: bool = True) -> httpx.AsyncClient:
    app = create_app(FakeProvider(), api_config(security=security, expose_docs=expose_docs))
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


def _assert_security_headers(response: httpx.Response, *, production: bool = False) -> None:
    for name, value in BASE_HEADERS.items():
        assert response.headers[name] == value, name
    assert "camera=()" in response.headers["permissions-policy"]
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert ("strict-transport-security" in response.headers) is production


async def _csrf(client: httpx.AsyncClient) -> dict[str, str]:
    token = (await client.get("/v1/auth/csrf")).json()["csrf_token"]
    return {"X-CSRF-Token": token}


async def test_every_response_class_carries_the_security_headers() -> None:
    async with _client() as client:
        headers = await _csrf(client)
        responses = {
            200: await client.get("/health/live"),
            401: await client.get("/v1/auth/me"),
            403: await client.post("/v1/auth/start", json={}),
            404: await client.get("/no-such-route"),
            405: await client.put("/health/live"),
            413: await client.post("/v1/auth/start", content=b"x" * 20000, headers=headers),
            422: await client.post("/v1/auth/start", json={"kind": "persona"}, headers=headers),
            503: await client.post("/v1/auth/start", json={"kind": "persona", "persona_id": "p-1"}, headers=headers),
        }
    for status, response in responses.items():
        assert response.status_code == status, (status, response.text)
        _assert_security_headers(response)
        if status >= 400:
            assert response.headers["content-type"] == "application/problem+json"
            assert response.json()["status"] == status


async def test_api_responses_are_not_cached_and_production_adds_hsts() -> None:
    production = SecurityConfig(production=True, csrf_secret=b"p" * 32, cors_allowed_origins=("https://bank.example",))
    async with _client(production, expose_docs=False) as client:
        live = await client.get("/health/live")
        me = await client.get("/v1/auth/me")
    _assert_security_headers(live, production=True)
    assert live.headers["strict-transport-security"] == HSTS
    assert "cache-control" not in live.headers
    assert me.headers["cache-control"] == "no-store"


async def test_the_development_docs_page_gets_its_own_csp() -> None:
    async with _client() as client:
        docs = await client.get("/docs")
    assert docs.status_code == 200
    assert docs.headers["content-security-policy"] == DOCS_CSP


async def test_a_chunked_body_over_the_limit_is_refused_like_a_declared_one() -> None:
    async def chunks() -> AsyncIterator[bytes]:
        for _ in range(20):
            yield b"y" * 1000

    async with _client() as client:
        headers = await _csrf(client)
        refused = await client.post("/v1/auth/start", content=chunks(), headers=headers)
    assert refused.status_code == 413
    assert refused.json()["type"].endswith("/payload-too-large")
    assert refused.json()["request_id"] == refused.headers["x-request-id"]


async def test_a_body_within_the_limit_reaches_validation_intact() -> None:
    async with _client() as client:
        headers = await _csrf(client)
        headers["Content-Type"] = "application/json"
        response = await client.post("/v1/auth/start", content=b'{"kind": "persona"}', headers=headers)
    assert response.status_code == 422
    assert {"loc": ["body", "persona", "persona_id"], "type": "missing"} in response.json()["errors"]


@pytest.mark.parametrize(("origin", "allowed"), [("http://localhost:5173", True), ("https://evil.example", False)])
async def test_cors_allows_credentials_only_for_allowlisted_origins(origin: str, allowed: bool) -> None:
    preflight_headers = {
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,x-csrf-token",
    }
    async with _client() as client:
        preflight = await client.options("/v1/auth/start", headers=preflight_headers)
        simple = await client.get("/health/live", headers={"Origin": origin})
    _assert_security_headers(preflight)
    if allowed:
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == origin
        assert preflight.headers["access-control-allow-credentials"] == "true"
        assert simple.headers["access-control-allow-origin"] == origin
    else:
        assert preflight.status_code == 400
        assert "access-control-allow-origin" not in simple.headers


def test_the_security_config_refuses_a_short_secret_and_missing_rate_classes() -> None:
    with pytest.raises(ValueError, match="16 bytes"):
        SecurityConfig(production=False, csrf_secret=b"short")
    with pytest.raises(ValueError, match="every rate class"):
        SecurityConfig(production=False, csrf_secret=b"k" * 32, rate_limits={})
