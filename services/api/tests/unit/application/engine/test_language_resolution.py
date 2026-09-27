"""Per-turn language resolution: detection, preferences, the language question, and short replies."""

from bank_agent.application.engine.language import resolve_language
from bank_agent.domain.intelligence import LanguageDetection
from bank_agent.domain.locale import Language
from bank_agent.testing.language import FAKE_DETECTOR


def detected(language: Language | None) -> LanguageDetection:
    return LanguageDetection(language=language, confidence=0.9 if language else 0.0, detector=FAKE_DETECTOR)


def resolve(language: Language | None, text: str, **known: object) -> tuple[Language | None, str]:
    fields = {"preference": None, "session_preference": None, "pending_text": None, **known}
    result = resolve_language(detected(language), text=text, **fields)  # type: ignore[arg-type]
    return result.language, result.text


def test_a_certain_detection_sets_the_language() -> None:
    assert resolve(Language.PT, "não reconheço uma compra") == (Language.PT, "não reconheço uma compra")


def test_a_short_reply_keeps_the_preference() -> None:
    assert resolve(Language.ES, "sí", preference=Language.PT) == (Language.PT, "sí")
    assert resolve(Language.ES, "no reconozco esa compra", preference=Language.PT)[0] is Language.ES


def test_uncertain_or_english_text_uses_the_preferences_or_asks() -> None:
    assert resolve(None, "ok", session_preference=Language.PT) == (Language.PT, "ok")
    assert resolve(Language.EN, "I lost my card") == (None, "I lost my card")


def test_the_answer_to_the_language_question_processes_the_original_text() -> None:
    assert resolve(None, "português", pending_text="TRX-1 cobrado") == (Language.PT, "TRX-1 cobrado")
    assert resolve(Language.ES, "no reconozco un cargo de ayer", pending_text="1234") == (
        Language.ES,
        "no reconozco un cargo de ayer",
    )
    assert resolve(None, "hmm", pending_text="1234") == (None, "1234")
