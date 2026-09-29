"""A question about a card's state that names "bloqueada" is a status question, never a block request."""

import pytest

from bank_agent.application.understanding.extraction import asks_card_state, card_action
from bank_agent.domain.cards import CardAction


@pytest.mark.parametrize(
    "text",
    [
        "¿Mi tarjeta está activa o bloqueada?",
        "¿Está bloqueada mi tarjeta?",
        "¿Sigue bloqueada mi tarjeta de débito?",
        "Meu cartão está ativo ou bloqueado?",
        "Meu cartão está bloqueado?",
        "O cartão ficou bloqueado?",
    ],
)
def test_a_state_question_is_recognized_and_asks_for_no_action(text: str) -> None:
    assert asks_card_state(text)
    assert card_action(text) is None


@pytest.mark.parametrize(
    "text", ["Bloquea mi tarjeta", "Quiero bloquear mi tarjeta, la perdí", "Quero bloquear meu cartão"]
)
def test_a_block_request_is_still_a_block(text: str) -> None:
    assert not asks_card_state(text)
    assert card_action(text) is CardAction.BLOCK
