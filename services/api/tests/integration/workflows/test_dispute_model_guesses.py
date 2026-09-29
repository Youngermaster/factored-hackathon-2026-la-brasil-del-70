"""Slots the model guessed are not used as the customer's words (phase 14b, found on the dev split): for "Não
reconheço uma cobrança de 750.000 na ELECTRO PAMPA" the local model returned an ISO date the message never named and
a currency the customer never said, the amount matched no transaction in the real currency, and P asked the customer
to choose from one option. A date the text does not contain and a currency the text does not state are dropped."""

import pytest
from pydantic import JsonValue

from bank_agent.testing.fake_llm import FakeLLM, ScriptedResponse
from bank_agent_scenarios import MX
from bank_agent_workflow_support import DISPUTE_SLOTS, NO_SIGNALS, SIGNALS, Backend
from bank_agent_workflows import build_harness

TEXT = "No reconozco un cargo de 1250 en FIXTURE MARKET"


def _guessing_model(currency: str, date: str | None) -> FakeLLM:
    fake = FakeLLM()
    fake.script(SIGNALS, ScriptedResponse(output=NO_SIGNALS))
    transaction: dict[str, JsonValue] = {"amount": "1250", "currency_hint": currency, "date_expression": date,
                   "merchant_text": "FIXTURE MARKET", "card_last4_hint": None, "channel_hint": None}  # fmt: skip
    output: dict[str, JsonValue] = {"transaction": transaction, "reason_candidates": ["unrecognized"],
              "intent_candidates": [{"intent": "dispute_new", "confidence": 1.0}]}  # fmt: skip
    fake.script(DISPUTE_SLOTS, ScriptedResponse(output=output))
    return fake


@pytest.mark.parametrize(("currency", "date"), [("USD", "2026-06-18"), ("USD", None), ("MXN", "2026-06-18")])
async def test_a_guessed_currency_or_date_does_not_hide_the_purchase(
    backend: Backend, currency: str, date: str | None
) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store, llm=_guessing_model(currency, date))
    session = harness.session(MX, step_up=True)
    reply = await harness.say(TEXT, session)
    assert reply.state == "OFFER_PROTECTIVE_BLOCK"
