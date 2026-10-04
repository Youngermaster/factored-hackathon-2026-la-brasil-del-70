"""A model's invented card hint must not select a card for an ambiguous protective block request."""

import pytest
from pydantic import JsonValue

from bank_agent.domain.actions import ToolName
from bank_agent.domain.product import ProductStatus
from bank_agent.domain.workflow import Outcome
from bank_agent_scenarios import PT
from bank_agent_workflow_support import Backend, scripted_llm
from bank_agent_workflows import build_harness


def _guessed_slots(card_type: str | None, last4: str | None) -> dict[str, JsonValue]:
    return {
        "card_hint": {"card_type": card_type, "last4": last4},
        "requested_action": "block",
        "block_reason_candidates": ["lost"],
    }


@pytest.mark.parametrize(
    ("message", "choice"),
    [
        ("Perdí mi tarjeta, bloquéala por favor", "la de débito"),
        ("Perdi meu cartão, bloqueie por favor", "o de débito"),
    ],
)
@pytest.mark.parametrize(
    ("card_type", "last4"),
    [("credit_card", None), (None, "2468"), ("credit_card", "2468")],
)
async def test_an_invented_card_hint_asks_before_confirming_a_block(
    backend: Backend, message: str, choice: str, card_type: str | None, last4: str | None
) -> None:
    harness = build_harness(
        backend.uow_factory, backend.session_store, llm=scripted_llm(card=_guessed_slots(card_type, last4))
    )
    session = harness.session(PT)
    asked = await harness.say(message, session)
    assert (asked.state, asked.outcome) == ("CLARIFY", Outcome.CLARIFIED)
    assert asked.response.card_action_confirmation is None
    assert "**** 2468" in asked.response.text
    assert "**** 1357" in asked.response.text
    record = await harness.record(session, asked.turn_id)
    assert all(call.tool is not ToolName.BLOCK_CARD for call in record.tool_calls)
    async with harness.uow_factory(session.access_context()) as uow:
        cards = await uow.products.list()
    assert all(card.status is ProductStatus.ACTIVE for card in cards)

    chosen = await harness.say(choice, session, asked.conversation_id)
    assert chosen.state == "CONFIRM_BLOCK"
    assert chosen.response.card_action_confirmation is not None
    assert chosen.response.card_action_confirmation.card_last4 == "1357"


@pytest.mark.parametrize(
    "message",
    [
        "Bloquea mi tarjeta de débito",
        "Bloqueie meu cartão de débito",
        "Bloquea mi tarjeta terminada en 1357",
        "Bloqueie meu cartão final 1357",
    ],
)
async def test_an_explicit_card_hint_overrides_the_models_guess(backend: Backend, message: str) -> None:
    harness = build_harness(
        backend.uow_factory, backend.session_store, llm=scripted_llm(card=_guessed_slots("credit_card", "2468"))
    )
    reply = await harness.say(message, harness.session(PT))
    assert reply.state == "CONFIRM_BLOCK"
    assert reply.response.card_action_confirmation is not None
    assert reply.response.card_action_confirmation.card_last4 == "1357"
