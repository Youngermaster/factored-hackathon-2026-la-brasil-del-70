"""CSRF, roles, customer isolation, request limits, and rate limits over HTTP."""

import re

import pytest
from fastapi import FastAPI

from bank_agent_api import ApiBackend, ApiClient

DUMMY_IDS = {"conversation_id": "conv-dummy", "handoff_id": "ho-dummy", "application_id": "app-dummy"}


def _state_changing_paths(app: FastAPI) -> list[str]:
    """Every operation that is not a GET, from the OpenAPI document, with dummy ids in its path."""
    paths = []
    for path, operations in app.openapi()["paths"].items():
        if set(operations) - {"get"}:
            paths.append(re.sub(r"\{(\w+)\}", lambda match: DUMMY_IDS[match.group(1)], path))
    return sorted(paths)


async def test_every_state_changing_route_refuses_a_missing_or_mismatched_csrf_token(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    paths = _state_changing_paths(harness.app)
    assert len(paths) == 15
    async with ApiClient(harness.app) as client, ApiClient(harness.app) as other:
        await client.login("persona-mx")
        foreign = await other.refresh_csrf()
        for path in paths:
            missing = await client.post(path, {}, csrf=False)
            mismatched = await client.post(path, {}, csrf=False, headers={"X-CSRF-Token": foreign})
            for response in (missing, mismatched):
                assert response.status_code == 403, (path, response.text)
                assert response.json()["type"].endswith("/csrf-token-invalid")


async def test_a_token_from_before_login_stops_working_after_login(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    async with ApiClient(harness.app) as client:
        anonymous = await client.refresh_csrf()
        await client.login("persona-mx")
        client.http.cookies.set("csrf", anonymous)
        refused = await client.post("/v1/conversations", headers={"X-CSRF-Token": anonymous}, csrf=False)
    assert refused.status_code == 403


@pytest.mark.parametrize(
    ("persona", "method", "path"),
    [
        ("persona-mx", "GET", "/v1/agent/handoffs/ho-dummy/human-service"),
        ("persona-mx", "POST", "/v1/agent/handoffs/ho-dummy/human-service/messages"),
        ("persona-agent", "GET", "/v1/conversations/conv-dummy/human-service"),
        ("persona-agent", "POST", "/v1/conversations/conv-dummy/human-service/messages"),
        ("persona-mx", "GET", "/v1/agent/handoffs"),
        ("persona-mx", "POST", "/v1/agent/handoffs/ho-dummy/claim"),
        ("persona-mx", "GET", "/v1/agent/credit-applications"),
        ("persona-mx", "GET", "/v1/eval/conversations/conv-dummy/trace"),
        ("persona-mx", "GET", "/v1/eval/summaries"),
        ("persona-agent", "POST", "/v1/conversations"),
        ("persona-agent", "GET", "/v1/conversations/conv-dummy"),
        ("persona-agent", "GET", "/v1/conversations/conv-dummy/trace"),
        ("persona-agent", "GET", "/v1/eval/conversations/conv-dummy/trace"),
        ("persona-evaluator", "GET", "/v1/conversations/conv-dummy"),
        ("persona-evaluator", "GET", "/v1/agent/handoffs"),
    ],
)
async def test_roles_are_enforced_per_route(api_backend: ApiBackend, persona: str, method: str, path: str) -> None:
    harness = api_backend.build()
    async with ApiClient(harness.app) as client:
        await client.login(persona)
        response = await (client.post(path) if method == "POST" else client.get(path))
    assert response.status_code == 403, response.text
    assert response.json()["type"].endswith("/role-not-permitted")


async def test_another_customers_conversation_is_indistinguishable_from_a_missing_one(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    async with ApiClient(harness.app) as owner, ApiClient(harness.app) as intruder:
        await owner.login("persona-mx")
        conversation = await owner.open_conversation()
        assert (await owner.get(f"/v1/conversations/{conversation}")).status_code == 200
        await intruder.login("persona-co")
        for path in (f"/v1/conversations/{conversation}", f"/v1/conversations/{conversation}/trace"):
            foreign, missing = await intruder.get(path), await intruder.get(path.replace(conversation, "conv-none"))
            assert foreign.status_code == missing.status_code == 404
            assert {k: v for k, v in foreign.json().items() if k not in ("instance", "request_id")} == {
                k: v for k, v in missing.json().items() if k not in ("instance", "request_id")
            }
        turn = await intruder.say(conversation, "Hola, ¿cuál es mi saldo?")
    assert turn.status_code == 404


async def test_request_limits_reject_oversized_and_unexpected_input(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    async with ApiClient(harness.app) as client:
        await client.login("persona-mx")
        conversation = await client.open_conversation()
        too_long = await client.say(conversation, "a" * 2001)
        empty = await client.say(conversation, "")
        unexpected = {"turn_id": "0b0e5a6c-6f6e-4d7e-9b6f-3f3f3f3f3f3f", "text": "hola", "role": "admin"}
        extra = await client.post(f"/v1/conversations/{conversation}/turns", unexpected)
        not_uuid = await client.post(f"/v1/conversations/{conversation}/turns", {"turn_id": "x", "text": "hola"})
        huge = await client.post(f"/v1/conversations/{conversation}/turns", {"turn_id": "t", "text": "b" * 20000})
    for response in (too_long, empty, extra, not_uuid):
        assert response.status_code == 422, response.text
    assert huge.status_code == 413


async def test_auth_rate_limits_per_ip_answer_429_with_retry_after(
    api_backend: ApiBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MINUTE", "3")
    harness = api_backend.build()
    async with ApiClient(harness.app) as client, ApiClient(harness.app, client_ip="203.0.113.99") as elsewhere:
        statuses = [(await client.get("/v1/auth/csrf")).status_code for _ in range(4)]
        refused = await client.get("/v1/auth/csrf")
        other_ip = await elsewhere.get("/v1/auth/csrf")
    assert statuses == [200, 200, 200, 429]
    assert refused.json()["type"].endswith("/rate-limited")
    assert 1 <= int(refused.headers["retry-after"]) <= 60
    assert other_ip.status_code == 200


async def test_session_rate_limits_follow_the_session_across_addresses(
    api_backend: ApiBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RATE_LIMIT_SESSION_READ_PER_MINUTE", "2")
    harness = api_backend.build()
    async with ApiClient(harness.app) as client, ApiClient(harness.app, client_ip="198.51.100.7") as moved:
        await client.login("persona-mx")
        first = [(await client.get("/v1/auth/me")).status_code for _ in range(2)]
        moved.http.cookies.set("session", str(client.http.cookies.get("session")))
        refused = await moved.get("/v1/auth/me")
    assert first == [200, 200]
    assert refused.status_code == 429
    assert "retry-after" in refused.headers


async def test_a_repeated_turn_id_replays_and_one_from_another_conversation_conflicts(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    async with ApiClient(harness.app) as client:
        await client.login("persona-mx")
        first_conversation = await client.open_conversation()
        second_conversation = await client.open_conversation()
        turn_id = "3f8a2c1e-9d4b-4e6f-8a7b-1c2d3e4f5a6b"
        original = await client.say(first_conversation, "Recomiéndame una inversión", turn_id)
        replayed = await client.say(first_conversation, "Recomiéndame una inversión", turn_id)
        conflict = await client.say(second_conversation, "Otra cosa", turn_id)
        history = await client.get(f"/v1/conversations/{first_conversation}")
    assert original.json()["replayed"] is False
    assert replayed.json()["replayed"] is True
    assert replayed.json()["message"] == original.json()["message"]
    assert conflict.status_code == 409
    turns = history.json()["turns"]
    assert [turn["customer_text"] for turn in turns] == ["Recomiéndame una inversión"]
    assert turns[0]["message"]["text"] == original.json()["message"]["text"]


async def test_two_workers_share_the_postgres_rate_limits(
    postgres_api: ApiBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "postgres")
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MINUTE", "3")
    first, second = postgres_api.build(), postgres_api.build()
    async with ApiClient(first.app) as one, ApiClient(second.app) as two:
        statuses = [
            (await one.get("/v1/auth/csrf")).status_code,
            (await two.get("/v1/auth/csrf")).status_code,
            (await one.get("/v1/auth/csrf")).status_code,
            (await two.get("/v1/auth/csrf")).status_code,
        ]
    assert first.container.rate_limit_store is not None
    assert statuses == [200, 200, 200, 429]
