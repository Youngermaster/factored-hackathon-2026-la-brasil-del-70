"""The lexical language detector: clear, mixed, and uncertain input in es, pt, and en."""

import pytest

from bank_agent.adapters.models.lexical_language import LEXICAL_DETECTOR, LexicalLanguageDetector, marker_counts
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.locale import Language

DETECTOR = LexicalLanguageDetector()


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("No reconozco un cargo de ayer en mi tarjeta", Language.ES),
        ("Che, vos me cobraste 15 lucas y no fui yo", Language.ES),
        ("Não reconheço uma cobrança no meu cartão", Language.PT),
        ("Quero bloquear o cartão que perdi ontem", Language.PT),
        ("I lost my card yesterday, please block it", Language.EN),
    ],
)
def test_detects_clear_text(text: str, language: Language) -> None:
    detection = DETECTOR.detect(UntrustedText(text))
    assert detection.language is language
    assert detection.detector == LEXICAL_DETECTOR


@pytest.mark.parametrize("text", ["1", "ok", "12345", "TRX-01Z3"])
def test_text_without_markers_is_uncertain(text: str) -> None:
    detection = DETECTOR.detect(UntrustedText(text))
    assert (detection.language, detection.confidence) == (None, 0.0)


def test_mixed_input_is_answered_in_the_dominant_language() -> None:
    detection = DETECTOR.detect(
        UntrustedText("Hola, tengo una duda: meu cartão não funciona e não consigo usar minha conta")
    )
    assert detection.is_mixed is True
    assert detection.language is Language.PT


def test_an_even_split_is_uncertain() -> None:
    detection = DETECTOR.detect(UntrustedText("hola obrigado"))
    assert detection.language is None
    assert detection.is_mixed is True


def test_orthography_counts_half_a_marker_and_shared_words_count_for_neither() -> None:
    counts = marker_counts("ação")
    assert counts[Language.PT] == 1.0
    assert marker_counts("perdi")[Language.ES] == 0.0
