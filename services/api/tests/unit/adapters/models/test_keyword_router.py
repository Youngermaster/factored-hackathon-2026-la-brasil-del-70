"""The keyword router table in Spanish, Portuguese, and English (fixture sentences written by the team)."""

import pytest

from bank_agent.adapters.models.keyword_router import KEYWORD_ROUTER, THRESHOLD, KeywordIntentRouter, score
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.locale import Language
from bank_agent.domain.workflow import Intent

ROUTER = KeywordIntentRouter()


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("No reconozco un cargo de 1250 pesos de ayer", Intent.DISPUTE_NEW),
        ("Che, vos me cobraste 15 lucas en el super y no fui yo", Intent.DISPUTE_NEW),
        ("Não reconheço uma cobrança no meu cartão", Intent.DISPUTE_NEW),
        ("Me cobraron dos veces la misma compra", Intent.DISPUTE_NEW),
        ("¿Cómo va mi reclamo?", Intent.DISPUTE_STATUS),
        ("Qual é o status do meu caso?", Intent.DISPUTE_STATUS),
        ("Quiero bloquear mi tarjeta", Intent.CARD_BLOCK),
        ("Perdí mi tarjeta, bloquéala por favor", Intent.CARD_BLOCK),
        ("Quero desbloquear meu cartão", Intent.CARD_UNBLOCK_REQUEST),
        ("Perdí mi tarjeta y quiero una nueva", Intent.CARD_REPLACEMENT_REQUEST),
        ("Roubaram meu cartão, preciso de um novo", Intent.CARD_REPLACEMENT_REQUEST),
        ("Quiero saber el estado de mi tarjeta", Intent.CARD_STATUS),
        ("Hola, meu cartão não funciona", Intent.CARD_STATUS),
        ("Quiero hablar con una persona", Intent.HUMAN_REQUEST),
        ("Quero falar com um atendente", Intent.HUMAN_REQUEST),
        ("¿Cuántos días tengo para reclamar?", Intent.INFORMATIONAL),
        ("Recomiéndame una inversión", Intent.UNSUPPORTED),
        ("Quero um aumento de limite", Intent.UNSUPPORTED),
        ("Quiero hacer una transferencia", Intent.UNSUPPORTED),
        ("Quiero un contracargo ya", Intent.UNSUPPORTED),
        ("Me garantizas el reembolso?", Intent.UNSUPPORTED),
        ("Quiero un préstamo", Intent.CREDIT_PRODUCT_INFO),
        ("¿Cuál es mi saldo?", Intent.BALANCE_INQUIRY),
        ("Hola", Intent.GREETING_OR_OTHER),
    ],
)
def test_routes_team_written_sentences(text: str, intent: Intent) -> None:
    prediction = ROUTER.route(UntrustedText(text), Language.ES)
    assert prediction.intent is intent
    assert prediction.model == KEYWORD_ROUTER


def test_unblock_is_never_read_as_a_block() -> None:
    assert Intent.CARD_BLOCK not in score("desbloquear mi tarjeta")


def test_unmatched_text_is_a_low_confidence_greeting_below_threshold() -> None:
    prediction = ROUTER.route(UntrustedText("necesito ayuda con algo"), Language.ES)
    assert (prediction.intent, prediction.confidence, prediction.below_threshold) == (
        Intent.GREETING_OR_OTHER,
        0.2,
        True,
    )


def test_a_weak_match_is_below_the_threshold_and_candidates_are_ranked() -> None:
    prediction = ROUTER.route(UntrustedText("tengo un reclamo"), Language.ES)
    assert prediction.below_threshold is (prediction.confidence < THRESHOLD)
    assert prediction.intent is Intent.DISPUTE_NEW
    scores = [candidate.score for candidate in prediction.candidates]
    assert scores == sorted(scores, reverse=True)


def test_more_matches_raise_the_score_up_to_the_cap() -> None:
    assert score("no reconozco este cargo indebido, no fui yo")[Intent.DISPUTE_NEW] == pytest.approx(0.95)
