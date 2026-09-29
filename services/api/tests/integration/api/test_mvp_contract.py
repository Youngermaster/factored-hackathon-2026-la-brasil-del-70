"""The Tuesday MVP contract over HTTP (step 0 of ``docs/plans/mvp-tuesday.md``): the profile the chat header shows
and the correlation id every turn response carries."""

import uuid
from typing import Any

import pytest

from bank_agent.testing.fake_llm import FakeLLM, ScriptedResponse
from bank_agent_api import AGENT_PERSONA, ApiBackend, ApiClient
from bank_agent_workflow_support import ACCOUNT_SLOTS, NO_SIGNALS, SIGNALS

NO_ACCOUNT_SLOTS = {"product_hint": None, "statement_period_expression": None, "payment": None}


def _account_llm() -> FakeLLM:
    fake = FakeLLM()
    fake.script(SIGNALS, ScriptedResponse(output=NO_SIGNALS))
    fake.script(ACCOUNT_SLOTS, ScriptedResponse(output=NO_ACCOUNT_SLOTS))
    return fake


def _json(response: Any, status: int = 200) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_the_profile_shows_the_session_customer_and_the_default_assistant(api_backend: ApiBackend) -> None:
    async with ApiClient(api_backend.build().app) as client:
        await client.login("persona-ar")
        profile = _json(await client.get("/v1/profile"))
    assert profile == {
        "customer_first_name": "Tomas",
        "assistant": {
            "name": "Luna",
            "avatar_id": "avatar-01",
            "avatar_url": "/avatars/avatar-01.png",
            "updated_at": None,
        },
    }


async def test_the_profile_needs_a_customer_session(api_backend: ApiBackend) -> None:
    async with ApiClient(api_backend.build().app) as client:
        assert (await client.get("/v1/profile")).status_code == 401
        await client.login(AGENT_PERSONA)
        assert (await client.get("/v1/profile")).status_code == 403


async def test_a_turn_response_carries_the_request_correlation_id(
    api_backend: ApiBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WORKFLOW_LLM_UNDERSTANDING", "true")
    async with ApiClient(api_backend.build(llm=_account_llm()).app) as client:
        await client.login("persona-ar")
        conversation = await client.open_conversation()
        chosen = "req-mvp-0123456789"
        turn = {"turn_id": str(uuid.uuid4()), "text": "¿Cuál es mi saldo?"}
        reply = await client.post(f"/v1/conversations/{conversation}/turns", turn, headers={"X-Request-ID": chosen})
        generated = await client.say(conversation, "¿Y mi saldo de ahorro?")
    body = _json(reply)
    assert body["correlation_id"] == chosen == reply.headers["X-Request-ID"]
    assert body["assistant_profile"] is None
    assert body["message"]["simulated_agent"] is None
    assert _json(generated)["correlation_id"] == generated.headers["X-Request-ID"] != chosen
