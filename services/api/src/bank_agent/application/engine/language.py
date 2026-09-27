"""Per-turn language resolution: detection, the conversation's preference, the session's, or a question.

Customer conversations are Spanish or Portuguese. A certain detection of es or pt sets the language (a short reply
of fewer than ``MIN_WORDS_TO_SWITCH`` words never overrides an existing preference, so "ok" or "sí" keeps it).
Otherwise the conversation's preference, then the session's, apply. English or uncertain text with no preference
gets the language question in both languages, and the original text is processed after the answer. Mixed input
arrives here already resolved to its dominant language by the detector.
"""

from dataclasses import dataclass

from bank_agent.application.understanding.answers import parse_language_choice
from bank_agent.domain.intelligence import LanguageDetection
from bank_agent.domain.locale import Language

CUSTOMER_LANGUAGES = frozenset({Language.ES, Language.PT})
MIN_WORDS_TO_SWITCH = 3


@dataclass(frozen=True)
class LanguageResolution:
    language: Language | None
    """``None`` means ask the language question."""
    text: str
    from_pending: bool = False


def resolve_language(
    detection: LanguageDetection,
    *,
    text: str,
    preference: Language | None,
    session_preference: Language | None,
    pending_text: str | None,
) -> LanguageResolution:
    detected = detection.language if detection.language in CUSTOMER_LANGUAGES else None
    long_enough = len(text.split()) >= MIN_WORDS_TO_SWITCH
    if pending_text is not None:
        choice = parse_language_choice(text)
        if choice is not None:
            return LanguageResolution(choice, pending_text, from_pending=True)
        if detected is not None and long_enough:
            return LanguageResolution(detected, text)
        return LanguageResolution(None, pending_text)
    if detected is not None and (preference is None or long_enough):
        return LanguageResolution(detected, text)
    for known in (preference, session_preference):
        if known in CUSTOMER_LANGUAGES:
            return LanguageResolution(known, text)
    return LanguageResolution(None, text)
