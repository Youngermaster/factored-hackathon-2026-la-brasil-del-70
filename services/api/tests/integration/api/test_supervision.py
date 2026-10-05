"""``GET /v1/eval/models`` over HTTP: evaluator only, the served models and cards, and nothing identifying."""

import json
import secrets
from typing import Any

import pytest

from bank_agent_api import AGENT_ID, EVALUATOR_ID, ApiBackend, ApiClient
from bank_agent_scenarios import MX

SECRET = secrets.token_urlsafe(32)
HIDDEN_KEYS = {"api_key", "api_base", "secret", "api_key_primary", "api_key_fallback", "local_path", "customer_id"}


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in _keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in _keys(item)}
    return set()


async def test_evaluators_read_the_served_models_and_their_offline_evidence(
    api_backend: ApiBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_API_KEY_PRIMARY", SECRET)
    harness = api_backend.build()
    async with ApiClient(harness.app) as customer:
        await customer.login("persona-mx")
        await customer.post("/v1/conversations", json={})
    async with ApiClient(harness.app) as evaluator:
        await evaluator.login("persona-evaluator")
        response = await evaluator.get("/v1/eval/models")
    assert response.status_code == 200
    body = response.json()
    served = {item["component"]: item["served"] for item in body["inventory"]["components"]}
    assert served == {
        "router": "router:keyword@1",
        "resolver": "resolver:rules@1",
        "risk_estimator": "risk_estimator:score_band@1",
        "retriever": "retriever:bm25@1",
        "language_detector": "language_detector:lexical@1",
    }
    assert body["inventory"]["llm"]["understanding"] is False
    assert body["cards"]["measurement"] == "offline"
    assert {card["component"] for card in body["cards"]["cards"]} >= {"router", "resolver", "risk_estimator"}
    assert len(body["cards"]["promotions"]) == 2
    text = json.dumps(body)
    for hidden in (SECRET, EVALUATOR_ID, AGENT_ID, MX, "/home/", "/app/"):
        assert hidden not in text
    assert not _keys(body) & HIDDEN_KEYS


async def test_agents_customers_and_anonymous_callers_cannot_read_the_inventory(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    async with ApiClient(harness.app) as anonymous, ApiClient(harness.app) as agent:
        refused = await anonymous.get("/v1/eval/models")
        await agent.login("persona-agent")
        forbidden = await agent.get("/v1/eval/models")
    async with ApiClient(harness.app) as customer:
        await customer.login("persona-mx")
        customer_forbidden = await customer.get("/v1/eval/models")
    assert refused.status_code == 401
    assert forbidden.status_code == 403
    assert forbidden.json()["type"].endswith("role-not-permitted")
    assert customer_forbidden.status_code == 403


async def test_a_broken_card_file_is_a_problem_that_names_nothing(
    memory_api: ApiBackend, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    broken = tmp_path / "cards.yaml"
    broken.write_text("cards: [{component: router, internal-detail: x}]\n", encoding="utf-8")
    monkeypatch.setenv("EVAL_MODEL_CARDS_FILE", str(broken))
    harness = memory_api.build()
    async with ApiClient(harness.app) as evaluator:
        await evaluator.login("persona-evaluator")
        response = await evaluator.get("/v1/eval/models")
    assert response.status_code == 500
    assert "internal-detail" not in response.text
    assert str(tmp_path) not in response.text
