"""Card support regressions from the 2026-10-05 production QA pass (CRD-02), in es and pt, driven through the
engine on the in-memory adapters with the deterministic fallback."""

from collections.abc import AsyncIterator

import pytest

from bank_agent.domain.workflow import Outcome
from bank_agent_scenarios import MX, PT
from bank_agent_workflow_support import Backend, memory_backend
from bank_agent_workflows import build_harness


@pytest.fixture
async def backend(request: pytest.FixtureRequest) -> AsyncIterator[Backend]:
    async for value in memory_backend(request):
        yield value


@pytest.mark.parametrize(
    ("customer", "ask", "choose", "expiry", "block", "last4"),
    [
        (MX, "¿Mi tarjeta está activa?", "la de crédito", "¿cuándo vence?", "bloquéala, la perdí", "1234"),
        (PT, "Qual é a situação do meu cartão?", "o de débito", "quando vence?", "bloqueia ele, perdi", "1357"),
    ],
)
async def test_a_status_follow_up_keeps_the_card_and_block_it_targets_that_card(
    backend: Backend, customer: str, ask: str, choose: str, expiry: str, block: str, last4: str
) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(customer, step_up=True)
    asked = await harness.say(ask, session)
    assert asked.state == "CLARIFY"
    chosen = await harness.say(choose, session, asked.conversation_id)
    assert chosen.state == "CARD_STATUS"
    assert last4 in chosen.response.text
    again = await harness.say(expiry, session, asked.conversation_id)
    assert again.state == "CARD_STATUS"
    assert again.outcome is not Outcome.CLARIFIED
    assert last4 in again.response.text
    blocked = await harness.say(block, session, asked.conversation_id)
    assert blocked.state == "CONFIRM_BLOCK"
    assert blocked.response.card_action_confirmation is not None
    assert blocked.response.card_action_confirmation.card_last4 == last4


async def test_a_block_request_while_choosing_a_card_is_kept_not_counted_as_a_failed_answer(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(MX, step_up=True)
    asked = await harness.say("¿Mi tarjeta está activa?", session)
    assert asked.state == "CLARIFY"
    blocked = await harness.say("ok bloquéala porfa, creo que la perdí", session, asked.conversation_id)
    assert blocked.outcome is not Outcome.ESCALATED
    assert blocked.state == "CONFIRM_BLOCK"
    assert blocked.response.card_action_confirmation is not None
    assert blocked.response.card_action_confirmation.card_last4 == "1234"
