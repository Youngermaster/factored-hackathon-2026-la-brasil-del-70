"""A card ending the customer has no card with (phase 14b, found on the dev split): P listed the customer's cards
before, but with the local model its card type hint narrowed the cards to one and P answered the status of a card
the customer did not name. A stated ending that matches none of the cards is now always asked about."""

import pytest

from bank_agent.domain.workflow import Outcome
from bank_agent.testing.fake_llm import FakeLLM, ScriptedResponse
from bank_agent_scenarios import CO, MX, PT
from bank_agent_workflow_support import CARD_SLOTS, NO_SIGNALS, SIGNALS, Backend
from bank_agent_workflows import build_harness

GUESS = {"card_hint": {"card_type": "debit_card", "last4": "4321"}, "requested_action": None,
         "block_reason_candidates": []}  # fmt: skip
ASK = {MX: "¿Cómo está mi tarjeta terminada en 4321?", PT: "Como está o meu cartão final 4321?"}
CARDS = {MX: "Es sobre mis tarjetas", PT: "É sobre os meus cartões"}


def _model_that_guesses_a_type() -> FakeLLM:
    fake = FakeLLM()
    fake.script(SIGNALS, ScriptedResponse(output=NO_SIGNALS))
    fake.script(CARD_SLOTS, ScriptedResponse(output=GUESS))
    return fake


@pytest.mark.parametrize("customer", [MX, PT])
async def test_an_unknown_card_ending_lists_the_customers_cards(backend: Backend, customer: str) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store, llm=_model_that_guesses_a_type())
    session = harness.session(customer)
    reply = await harness.say(ASK[customer], session)
    if reply.response.template_id == "common.clarify_workflow":  # the keyword router asks the workflow first
        reply = await harness.say(CARDS[customer], session, reply.conversation_id)
    assert (reply.state, reply.outcome) == ("CLARIFY", Outcome.CLARIFIED)
    assert reply.response.template_id == "card.clarify_options"
    assert "4321" not in reply.response.text


async def test_a_known_ending_is_still_chosen_directly(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(CO)
    reply = await harness.say("¿Cómo está mi tarjeta terminada en 9999?", session)
    if reply.response.template_id == "common.clarify_workflow":
        reply = await harness.say(CARDS[MX], session, reply.conversation_id)
    assert reply.outcome is Outcome.RESOLVED
    assert "**** 9999" in reply.response.text
