"""Deadline, definition, and how-it-works questions reach open retrieval (rubric audit 2026-10-05, fix 1), es and pt."""

import pytest

from bank_agent.adapters.models.keyword_router import KeywordIntentRouter
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.locale import Language
from bank_agent.domain.workflow import Intent

ROUTER = KeywordIntentRouter()


def _route(text: str, language: Language = Language.ES) -> tuple[Intent, bool]:
    prediction = ROUTER.route(UntrustedText(text), language)
    return prediction.intent, prediction.below_threshold


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("¿Cuántos días tengo para levantar una aclaración?", Language.ES),
        ("¿Cuál es el plazo para presentar una aclaración?", Language.ES),
        ("¿Cuánto tiempo tengo para desconocer un consumo?", Language.ES),
        ("¿Cuántos días tengo para aclarar un cargo que no reconozco?", Language.ES),
        ("Quantos dias tenho para abrir uma contestação?", Language.PT),
        ("Qual é o prazo para contestar uma compra?", Language.PT),
    ],
)
def test_a_deadline_question_routes_to_retrieval_not_dispute_intake(text: str, language: Language) -> None:
    assert _route(text, language) == (Intent.INFORMATIONAL, False)


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("¿Qué es un bloqueo preventivo de tarjeta?", Language.ES),
        ("¿Qué significa una aclaración?", Language.ES),
        ("O que é um bloqueio preventivo de cartão?", Language.PT),
        ("¿Cómo funciona el bloqueo preventivo?", Language.ES),
    ],
)
def test_a_definition_question_routes_to_retrieval_not_card_support(text: str, language: Language) -> None:
    assert _route(text, language) == (Intent.INFORMATIONAL, False)


@pytest.mark.parametrize(
    ("text", "language", "intent"),
    [
        ("Quiero levantar una aclaración por un cobro que no hice", Language.ES, Intent.DISPUTE_NEW),
        ("Quero abrir uma contestação de uma compra", Language.PT, Intent.DISPUTE_NEW),
        ("No reconozco un cargo", Language.ES, Intent.DISPUTE_NEW),
        ("Não reconheço uma compra no meu cartão", Language.PT, Intent.DISPUTE_NEW),
        ("bloquea mi tarjeta", Language.ES, Intent.CARD_BLOCK),
        ("Quero bloquear meu cartão", Language.PT, Intent.CARD_BLOCK),
        ("¿Cuánto tiempo tarda en bloquearse mi tarjeta?", Language.ES, Intent.CARD_BLOCK),
        ("¿Qué es este cargo de 500 pesos? No lo hice", Language.ES, Intent.DISPUTE_NEW),
        ("¿Hasta cuándo tengo que pagar?", Language.ES, Intent.UNSUPPORTED),
    ],
)
def test_intake_actions_and_own_account_questions_keep_their_workflow(
    text: str, language: Language, intent: Intent
) -> None:
    assert _route(text, language) == (intent, False)
