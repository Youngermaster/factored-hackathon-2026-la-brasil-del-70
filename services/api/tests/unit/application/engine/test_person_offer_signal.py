"""The keyword signal reads a bare yes as a request for a person only right after an offer of one."""

import pytest

from bank_agent.application.engine.signals import accepts_offer, detect_signals


@pytest.mark.parametrize("text", ["sí", "Sim", "claro", "sí, por favor", "dale", "sim, pode ser"])
def test_a_bare_yes_accepts_an_offer(text: str) -> None:
    assert accepts_offer(text)
    assert detect_signals(text, person_offered=True).human_requested
    assert not detect_signals(text).human_requested


@pytest.mark.parametrize("text", ["no", "não", "sí, ¿y cuál es mi saldo en la cuenta?", "no sé", "Quiero mi saldo"])
def test_anything_else_is_not_an_acceptance(text: str) -> None:
    assert not accepts_offer(text)
    assert not detect_signals(text, person_offered=True).human_requested
