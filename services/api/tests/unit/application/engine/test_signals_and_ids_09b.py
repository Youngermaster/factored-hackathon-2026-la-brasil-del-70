"""Session 09b additions to the untrusted-content checks: over-indebtedness is a distress signal, and credit
application ids named in the text are found so the engine can check them against the session's own records."""

import pytest

from bank_agent.application.engine.security import referenced_ids
from bank_agent.application.engine.signals import detect_signals


@pytest.mark.parametrize(
    "text",
    ["No puedo pagar mis deudas", "estoy muy endeudado", "estou endividada", "não consigo pagar minhas dívidas",
     "no llego a fin de mes"],
)  # fmt: skip
def test_over_indebtedness_is_a_distress_signal(text: str) -> None:
    assert detect_signals(text).distress


@pytest.mark.parametrize("text", ["quiero un préstamo para consolidar mis deudas", "quero um empréstimo"])
def test_a_debt_consolidation_request_is_not_distress(text: str) -> None:
    assert not detect_signals(text).distress


def test_application_ids_are_referenced() -> None:
    found = referenced_ids("¿Cuál es el estado de mi solicitud APP-000123 y del caso case-000001?")
    assert found.applications == ("app-000123",)
    assert found.cases == ("case-000001",)
    assert found.any
