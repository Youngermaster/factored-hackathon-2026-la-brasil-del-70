"""``scope:lexicon@1``: unrelated topics are off topic, bank-side requests the assistant never handles are a
service request, and greetings and plausible banking requests (even vague ones) keep the existing route."""

import pytest

from bank_agent.application.understanding.scope import Scope, classify_scope


@pytest.mark.parametrize(
    "text",
    [
        "¿Quién es mejor CR7 o Messi?",
        "Quem é melhor, CR7 ou Messi?",
        "¿Va a llover mañana en Bogotá?",
        "Vai chover amanhã em São Paulo?",
        "Dame una receta de arepas",
        "Me passa uma receita de bolo de cenoura",
        "¿Quién ganó las elecciones presidenciales?",
        "¿Cuál es la capital de Francia?",
        "Cuéntame un chiste",
        "Una pregunta: ¿quién ganó el partido de ayer?",
        "Who is better, CR7 or Messi?",
    ],
)
def test_an_unrelated_topic_is_off_topic(text: str) -> None:
    assert classify_scope(text) is Scope.OFF_TOPIC


@pytest.mark.parametrize(
    "text",
    [
        "Actualiza mi correo electrónico, por favor",
        "Atualize o meu e-mail, por favor",
        "Quiero cambiar mi número de teléfono",
        "Quero mudar o meu endereço",
        "¿Cómo declaro mis impuestos de este año?",
        "Como faço a minha declaração de imposto de renda deste ano?",
    ],
)
def test_a_bank_side_request_the_assistant_never_handles_is_a_service_request(text: str) -> None:
    assert classify_scope(text) is Scope.SERVICE


@pytest.mark.parametrize(
    "text",
    [
        "Tengo un problema",
        "Necesito ayuda",
        "Ayuda con mi cuenta",
        "Preciso de ajuda",
        "Estou com um problema",
        "¿Puedo pagar la entrada del partido con mi tarjeta?",
        "Mandei dinheiro para JUAN PEREZ e não sei se chegou",
        "Necesito el resumen de movimientos de mi tarjeta de crédito",
        "¿Cómo viene mi reclamo?",
        "Voy a viajar a España, activa mi tarjeta para usarla en el extranjero",
    ],
)
def test_a_plausible_banking_request_is_banking(text: str) -> None:
    assert classify_scope(text) is Scope.BANKING


@pytest.mark.parametrize(
    "text", ["hola", "Hola, buenos días", "Bom dia!", "Oi, tudo bem?", "gracias", "obrigado", "sí", "español", "1250"]
)
def test_a_greeting_or_a_bare_answer_is_courtesy(text: str) -> None:
    assert classify_scope(text) is Scope.COURTESY
