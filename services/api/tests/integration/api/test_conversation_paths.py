"""The normal path of each workflow through the HTTP API, plus an out-of-scope request, with a scripted FakeLLM.

Writes need a step-up: the card block asks for it mid-conversation and resumes after the step-up route; the dispute
and the credit intake step up first. Every reply part the frontend renders comes through the turn response.
"""

from typing import Any

import pytest
from pydantic import JsonValue

from bank_agent.testing.fake_llm import FakeLLM, ScriptedResponse
from bank_agent_api import ApiBackend, ApiClient
from bank_agent_workflow_support import ACCOUNT_SLOTS, CARD_SLOTS, CREDIT_SLOTS, DISPUTE_SLOTS, NO_SIGNALS, SIGNALS


def scripted(**outputs: dict[str, JsonValue]) -> FakeLLM:
    fake = FakeLLM()
    fake.script(SIGNALS, ScriptedResponse(output=NO_SIGNALS))
    prompts = {"account": ACCOUNT_SLOTS, "card": CARD_SLOTS, "credit": CREDIT_SLOTS, "dispute": DISPUTE_SLOTS}
    for name, output in outputs.items():
        fake.script(prompts[name], ScriptedResponse(output=output))
    return fake


@pytest.fixture(autouse=True)
def _understanding_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKFLOW_LLM_UNDERSTANDING", "true")


def _message(response: Any) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_account_inquiry_balances_state_their_as_of_date(api_backend: ApiBackend) -> None:
    llm = scripted(account={"product_hint": None, "statement_period_expression": None, "payment": None})
    harness = api_backend.build(llm=llm)
    async with ApiClient(harness.app) as client:
        await client.login("persona-ar")
        conversation = await client.open_conversation()
        reply = _message(await client.say(conversation, "Hola, ¿me decís cuál es mi saldo?"))
    assert (reply["workflow"]["id"], reply["state"], reply["outcome"]) == ("account_inquiry", "BALANCES", "resolved")
    message = reply["message"]
    assert "con datos al 17 de junio de 2026" in message["text"]
    assert message["balances"]
    assert all(balance["as_of"] for balance in message["balances"])
    assert "ACC-ALL-1@1" in [citation["clause"] for citation in message["citations"]]
    assert all(citation["excerpt"] for citation in message["citations"])


async def test_card_block_asks_for_step_up_and_resumes_after_the_step_up_route(api_backend: ApiBackend) -> None:
    llm = scripted(card={"card_hint": None, "requested_action": "block", "block_reason_candidates": ["lost"]})
    harness = api_backend.build(llm=llm)
    async with ApiClient(harness.app) as client:
        await client.login("persona-co")
        conversation = await client.open_conversation()
        confirm = _message(await client.say(conversation, "Perdí mi tarjeta, bloquéala por favor"))
        assert confirm["state"] == "CONFIRM_BLOCK"
        assert confirm["message"]["card_action_confirmation"]["reason"] == "lost"
        asked = _message(await client.say(conversation, "sí"))
        assert (asked["state"], asked["message"]["step_up_required"]) == ("EXECUTE", True)
        await client.step_up()
        done = _message(await client.say(conversation, "listo, ya verifiqué"))
    assert (done["state"], done["outcome"]) == ("RESOLVED", "resolved")
    assert "bloqueamos tu tarjeta de crédito **** 9999" in done["message"]["text"]
    (status,) = done["message"]["action_statuses"]
    assert (status["action"], status["status"]) == ("block_card", "verified")
    assert status["evidence"]


async def test_dispute_intake_is_confirmed_created_and_verified(api_backend: ApiBackend) -> None:
    extraction: dict[str, JsonValue] = {
        "intent_candidates": [{"intent": "dispute_new", "confidence": 0.93}],
        "transaction": {"amount": "1250", "currency_hint": "MXN", "merchant_text": "FIXTURE MARKET",
                        "date_expression": "el 15 de junio", "channel_hint": None, "card_last4_hint": None},
        "reason_candidates": ["unrecognized"],
    }  # fmt: skip
    harness = api_backend.build(llm=scripted(dispute=extraction))
    async with ApiClient(harness.app) as client:
        await client.login("persona-mx")
        await client.step_up()
        conversation = await client.open_conversation()
        first = _message(
            await client.say(conversation, "No reconozco un cargo de 1250 pesos en FIXTURE MARKET del 15 de junio")
        )
        assert first["state"] == "OFFER_PROTECTIVE_BLOCK"
        summary = _message(await client.say(conversation, "no, gracias"))
        assert summary["state"] == "CONFIRM_SUMMARY"
        assert summary["message"]["confirmation"]["reason"] == "unrecognized"
        done = _message(await client.say(conversation, "sí"))
    assert (done["workflow"]["id"], done["state"], done["outcome"]) == ("dispute", "RESOLVED", "resolved")
    assert [s["status"] for s in done["message"]["action_statuses"]] == ["verified"]


async def test_credit_eligibility_is_indicative_and_the_intake_is_recorded(api_backend: ApiBackend) -> None:
    slots: dict[str, JsonValue] = {"product_of_interest": "credit_card", "requested_amount": "30000",
                                   "currency_hint": "MXN", "requested_term_months": None, "purpose": None,
                                   "declared_monthly_income": None}  # fmt: skip
    harness = api_backend.build(llm=scripted(credit=slots))
    async with ApiClient(harness.app) as client:
        await client.login("persona-pt", language="pt")
        await client.step_up()
        conversation = await client.open_conversation()
        explained = _message(
            await client.say(conversation, "Sou elegível para um cartão de crédito com limite de 30 mil pesos?")
        )
        assert (explained["workflow"]["id"], explained["state"]) == ("credit", "EXPLAIN_ELIGIBILITY")
        eligibility = explained["message"]["eligibility"]
        assert (eligibility["outcome"], eligibility["synthetic"]) == ("indicatively_eligible", True)
        confirm = _message(await client.say(conversation, "sim"))
        assert confirm["message"]["credit_intake_confirmation"]["planned_actions"] == ["submit_credit_application"]
        done = _message(await client.say(conversation, "sim"))
    assert (done["state"], done["outcome"]) == ("RESOLVED", "resolved")
    assert done["message"]["action_statuses"][0]["status"] == "verified"


async def test_an_out_of_scope_request_abstains_at_the_router(api_backend: ApiBackend) -> None:
    harness = api_backend.build(llm=scripted())
    async with ApiClient(harness.app) as client:
        await client.login("persona-mx")
        conversation = await client.open_conversation()
        reply = _message(await client.say(conversation, "Recomiéndame una inversión para mis ahorros"))
    assert (reply["workflow"]["id"], reply["state"], reply["outcome"]) == ("router", "ABSTAINED", "abstained")
    assert {"SCOPE-ALL-1@1", "SCOPE-ALL-2@1"} <= {citation["clause"] for citation in reply["message"]["citations"]}
