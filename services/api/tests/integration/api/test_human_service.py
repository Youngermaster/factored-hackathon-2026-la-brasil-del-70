"""Real customer and human agent exchange over HTTP on both persistence backends."""

from uuid import uuid4

import pytest

from bank_agent_api import ApiBackend, ApiClient


async def test_human_exchange_survives_refresh_and_close_without_exposing_the_transcript(
    api_backend: ApiBackend,
) -> None:
    harness = api_backend.build()
    async with ApiClient(harness.app) as customer, ApiClient(harness.app) as agent, ApiClient(harness.app) as other:
        await customer.login("persona-mx", language="es")
        conversation = await customer.open_conversation()
        escalated = await customer.say(conversation, "Quiero hablar con una persona")
        assert escalated.status_code == 200
        handoff_id = escalated.json()["message"]["escalation"]["handoff_id"]
        customer_path = f"/v1/conversations/{conversation}/human-service"
        agent_path = f"/v1/agent/handoffs/{handoff_id}/human-service"
        queued = await customer.get(customer_path)
        assert queued.status_code == 200
        assert queued.json()["status"] == "queued"
        body = {"message_id": str(uuid4()), "text": "Necesito aclarar un cargo"}
        sent = await customer.post(customer_path + "/messages", body)
        assert sent.status_code == 200
        await agent.login("persona-agent")
        assert (await agent.get(agent_path)).status_code == 404
        claimed = await agent.post(f"/v1/agent/handoffs/{handoff_id}/claim")
        assert claimed.status_code == 200
        joined = await customer.get(customer_path)
        assert joined.json()["status"] == "joined"
        reply = await agent.post(
            agent_path + "/messages", {"message_id": str(uuid4()), "text": "Estoy revisando tu caso"}
        )
        assert reply.status_code == 200
        assert reply.json()["message"]["role"] == "agent"
        assert reply.json()["message"]["conversation_id"] == conversation
        history = await customer.get(customer_path)
        assert [m["text"] for m in history.json()["messages"]] == [body["text"], "Estoy revisando tu caso"]
        assert "staff_id" not in str(history.json())
        assert "credit_review" not in str(history.json())
        assert "turns" not in (await agent.get(agent_path)).json()
        await other.login("persona-co")
        assert (await other.get(customer_path)).status_code == 404
        resolved = await agent.post(
            f"/v1/agent/handoffs/{handoff_id}/resolve", {"outcome": "resolved_by_agent", "note": "Explained"}
        )
        assert resolved.status_code == 200
        closed = await customer.get(customer_path)
        assert closed.json()["status"] == "closed"
        assert closed.json()["closed_at"] is not None
        assert (await customer.get(f"/v1/conversations/{conversation}")).json()["conversation"]["status"] == "closed"
        assert (await customer.say(conversation, "Otra consulta")).status_code == 409
        assert len(closed.json()["messages"]) == 2
        assert (await customer.post(customer_path + "/messages", body)).json()["replayed"]
        rejected = await customer.post(
            customer_path + "/messages", {"message_id": str(uuid4()), "text": "Otro mensaje"}
        )
        assert rejected.status_code == 409
        page = await agent.get(agent_path, params={"after": 1})
        assert [m["role"] for m in page.json()["messages"]] == ["agent"]


async def test_human_channel_rejects_forged_authors_csrf_and_evaluator_access(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    async with ApiClient(harness.app) as customer, ApiClient(harness.app) as evaluator:
        await customer.login("persona-pt", language="pt")
        conversation = await customer.open_conversation()
        escalated = await customer.say(conversation, "Quero falar com uma pessoa")
        assert escalated.status_code == 200
        path = f"/v1/conversations/{conversation}/human-service/messages"
        body = {"message_id": str(uuid4()), "text": "Preciso de ajuda"}
        assert (await customer.post(path, body, csrf=False)).status_code == 403
        assert (await customer.post(path, {**body, "role": "agent"})).status_code == 422
        assert (await customer.post(path, {**body, "customer_id": "another"})).status_code == 422
        assert (await customer.post(path, {**body, "text": " "})).status_code == 422
        assert (await customer.post(path, {**body, "text": "x" * 4001})).status_code == 422
        await evaluator.login("persona-evaluator")
        assert (await evaluator.post(path, body)).status_code == 403


async def test_chat_creation_quota_follows_customer_across_sessions_and_excludes_messages(
    api_backend: ApiBackend,
) -> None:
    from datetime import timedelta

    harness = api_backend.build()
    async with ApiClient(harness.app) as first, ApiClient(harness.app) as second, ApiClient(harness.app) as other:
        await first.login("persona-mx")
        await second.login("persona-mx")
        await other.login("persona-co")
        conversations = [await first.open_conversation() for _ in range(3)]
        conversations.extend([await second.open_conversation() for _ in range(2)])
        assert len(set(conversations)) == 5
        blocked = await second.post("/v1/conversations")
        assert blocked.status_code == 429
        assert blocked.headers["Retry-After"] == "3600"
        assert blocked.json()["type"].endswith("conversation-creation-limited")
        assert (await other.post("/v1/conversations")).status_code == 201
        result = await first.say(conversations[0], "Quiero hablar con una persona")
        assert result.status_code == 200
        path = f"/v1/conversations/{conversations[0]}/human-service/messages"
        for _ in range(6):
            assert (await second.post(path, {"message_id": str(uuid4()), "text": "Más detalles"})).status_code == 200
        assert (await first.post("/v1/conversations")).status_code == 429
        harness.clock.advance(timedelta(hours=1))
        await second.login("persona-mx")
        assert (await second.post("/v1/conversations")).status_code == 201


async def test_a_configured_creation_quota_answers_429_with_its_problem_type_and_window(
    api_backend: ApiBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import timedelta

    monkeypatch.setenv("CONVERSATION_CREATION_LIMIT", "2")
    monkeypatch.setenv("CONVERSATION_CREATION_WINDOW_MINUTES", "10")
    harness = api_backend.build()
    async with ApiClient(harness.app) as customer:
        await customer.login("persona-ar")
        assert len({await customer.open_conversation() for _ in range(2)}) == 2
        blocked = await customer.post("/v1/conversations")
        assert blocked.status_code == 429
        assert blocked.headers["content-type"].startswith("application/problem+json")
        assert blocked.headers["Retry-After"] == "600"
        problem = blocked.json()
        assert problem["type"].endswith("/conversation-creation-limited")
        assert problem["status"] == 429
        assert "five" not in str(problem).lower()
        harness.clock.advance(timedelta(minutes=10))
        await customer.login("persona-ar")
        assert (await customer.post("/v1/conversations")).status_code == 201
