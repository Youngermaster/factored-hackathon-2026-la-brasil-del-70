"""Card block follow-ups must honor the current card choice and discard completed-request hints."""

import pytest

from bank_agent.domain.actions import ToolName
from bank_agent.domain.product import ProductStatus
from bank_agent.domain.workflow import Outcome
from bank_agent_scenarios import PT
from bank_agent_workflow_support import Backend
from bank_agent_workflows import build_harness


@pytest.mark.parametrize(
    ("status_message", "block_message"),
    [
        ("Estado de mi tarjeta de crédito terminada en 2468", "Bloquea mi tarjeta de débito"),
        ("Situação do meu cartão de crédito final 2468", "Bloqueie meu cartão de débito"),
        ("Estado de mi tarjeta de crédito", "Bloquea mi tarjeta terminada en 1357"),
        ("Situação do meu cartão de crédito", "Bloqueie meu cartão final 1357"),
    ],
)
async def test_a_block_follow_up_naming_another_card_confirms_and_blocks_that_card(
    backend: Backend, status_message: str, block_message: str
) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(PT, step_up=True)
    first = await harness.say(status_message, session)
    assert first.state == "CARD_STATUS"
    confirmation = await harness.say(block_message, session, first.conversation_id)
    assert confirmation.state == "CONFIRM_BLOCK"
    assert confirmation.response.card_action_confirmation is not None
    assert confirmation.response.card_action_confirmation.card_last4 == "1357"
    assert confirmation.response.action_statuses == ()

    done = await harness.say("sim", session, first.conversation_id)
    assert (done.state, done.outcome) == ("RESOLVED", Outcome.RESOLVED)
    async with harness.uow_factory(session.access_context()) as uow:
        cards = {str(card.product_id): card for card in await uow.products.list()}
    assert cards["PRD-FIXPT-DEB"].status is ProductStatus.BLOCKED
    assert cards["PRD-FIXPT-CRED"].status is ProductStatus.ACTIVE


@pytest.mark.parametrize(
    ("first_message", "next_message"),
    [
        ("Bloquea mi tarjeta de crédito", "Perdí mi tarjeta, bloquéala por favor"),
        ("Bloqueie meu cartão de crédito", "Perdi meu cartão, bloqueie por favor"),
    ],
)
async def test_a_new_request_after_cancellation_does_not_reuse_the_previous_card_hint(
    backend: Backend, first_message: str, next_message: str
) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(PT, step_up=True)
    first = await harness.say(first_message, session)
    assert first.state == "CONFIRM_BLOCK"
    cancelled = await harness.say("no", session, first.conversation_id)
    assert cancelled.outcome is Outcome.RESOLVED
    asked = await harness.say(next_message, session, first.conversation_id)
    assert (asked.state, asked.outcome) == ("CLARIFY", Outcome.CLARIFIED)
    assert asked.response.card_action_confirmation is None
    record = await harness.record(session, asked.turn_id)
    assert all(call.tool is not ToolName.BLOCK_CARD for call in record.tool_calls)


@pytest.mark.parametrize(
    "message",
    ["Bloquea mi tarjeta de débito terminada en 2468", "Bloqueie meu cartão de débito final 2468"],
)
async def test_conflicting_card_type_and_ending_ask_instead_of_selecting_a_different_card(
    backend: Backend, message: str
) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    reply = await harness.say(message, harness.session(PT))
    assert (reply.state, reply.outcome) == ("CLARIFY", Outcome.CLARIFIED)
    assert reply.response.card_action_confirmation is None
