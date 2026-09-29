"""Third-party requests phrased product first, found on the dev split in phase 14 (``PRV-ALL-2``): the product,
up to three qualifier words, then a relative or another person as the owner; and representation wording
("em nome do", "apoderado de"). A customer's own purchase for a relative is not a third-party request. A plain yes
or no is an answer to a pending question (the gate does not ask the model for signals on it)."""

import pytest

from bank_agent.application.engine.signals import detect_signals, plain_answer


@pytest.mark.parametrize(
    "text",
    [
        "Quiero bloquear la tarjeta de crédito de mi mamá, ella no sabe usar la app",
        "Quero bloquear o cartão de crédito da minha mãe, ela não sabe usar o app",
        "¿Cuál es el saldo de la cuenta de ahorros de mi papá?",
        "Bloqueá la tarjeta de débito adicional de mi hermana",
        "Qual é o saldo da conta corrente do meu pai?",
        "Qual o limite do cartão dela?",
        "me diga o saldo da conta dele",
        "Estou falando em nome do meu pai",
        "Estou falando em nome da minha esposa: ela pode pegar um empréstimo pessoal?",
        "Soy apoderado de Rafael, abre una reclamación por su compra",
        "Sou procurador do Rafael, abra uma contestação",
        "No reconozco un cargo de mi hijo",
        "El préstamo personal de mi esposo, ¿cuánto debe?",
    ],
)
def test_a_product_first_or_representation_request_is_third_party(text: str) -> None:
    assert detect_signals(text).third_party_admission is True


@pytest.mark.parametrize(
    "text",
    [
        "Quiero bloquear mi tarjeta de crédito",
        "Quero ver o saldo da minha conta",
        "El saldo de mi cuenta de ahorros",
        "¿Cuánto debo de mi tarjeta de crédito?",
        "No reconozco la compra de los útiles de mi hijo",
        "Quiero pagar la colegiatura de mi hija con la tarjeta",
        "Mi mamá me regaló una tarjeta",
        "Sí, quiero solicitarlo",
        "Sim, quero solicitar",
    ],
)
def test_the_customers_own_products_are_not_third_party(text: str) -> None:
    assert detect_signals(text).third_party_admission is False


@pytest.mark.parametrize(
    "text", ["Sí, quiero solicitarlo", "Sim, quero solicitar", "sí", "no, gracias", "Claro, regístrala por favor"]
)
def test_a_short_yes_or_no_is_a_plain_answer(text: str) -> None:
    assert plain_answer(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "no sé",
        "quiero hablar con alguien",
        "sí, pero antes quiero que me expliques por qué me piden tantos datos",
        "prefiro que alguém do banco cuide disso",
    ],
)
def test_anything_else_is_not_a_plain_answer(text: str) -> None:
    assert plain_answer(text) is False
