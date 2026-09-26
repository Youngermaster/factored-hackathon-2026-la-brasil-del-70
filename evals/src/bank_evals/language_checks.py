"""Deterministic checks that a customer-facing reply is written in the expected language.

The main use is Brazilian Portuguese: a reply must read as natural pt-BR, not translated Spanish. The check is
lexical and conservative. It flags Spanish-only words and punctuation (``usted``, ``tarjeta``, the inverted
question and exclamation marks, the letter ``ñ``) and requires at least one clearly Portuguese marker
(``você``, ``não``, ``cartão``, words ending in ``ção``). It cannot judge fluency; phase 14 adds human review of a
sample of recorded replies. The Spanish check mirrors it, so a Portuguese reply in a Spanish session is caught
too.

These checks run over cassettes (hand-authored fixtures today, recorded replies once a provider is chosen) and
over evaluation transcripts.
"""

import re
from typing import Final

SPANISH_ONLY_WORDS: Final[frozenset[str]] = frozenset(
    {
        "usted",
        "ustedes",
        "tarjeta",
        "tarjetas",
        "cuenta",
        "cuentas",
        "préstamo",
        "gracias",
        "señor",
        "señora",
        "ahorros",
        "quedó",
        "hemos",
        "está bien",
        "le ayudo",
        "necesita",
        "solicitud",
        "monto",
        "plazo",
        "días hábiles",
        "y",
        "el",
        "los",
        "las",
        "del",
        "su",
        "sus",
        "pero",
        "muy",
    }
)
"""Words and phrases that do not occur in Brazilian Portuguese (``y``, ``el``, ``los`` and ``del`` are Spanish
function words; the Portuguese equivalents are ``e``, ``o``, ``os`` and ``do``)."""

PORTUGUESE_MARKERS: Final[frozenset[str]] = frozenset(
    {"você", "vocês", "não", "cartão", "conta", "seu", "sua", "é", "às", "prazo", "pedido", "obrigado", "obrigada"}
)
PORTUGUESE_ONLY_WORDS: Final[frozenset[str]] = frozenset(
    {"você", "vocês", "não", "cartão", "seu", "sua", "às", "obrigado", "obrigada", "então", "também", "já", "ao"}
)
SPANISH_MARKERS: Final[frozenset[str]] = frozenset(
    {"usted", "su", "tarjeta", "cuenta", "el", "la", "los", "del", "es", "de", "por"}
)
_SPANISH_PUNCTUATION = re.compile(r"[¿¡ñÑ]")
_PORTUGUESE_ORTHOGRAPHY = re.compile(r"(ção|ções|ão|ões|nh|lh)\b|[ãõ]", re.IGNORECASE)


def _contains(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(phrase)}(?![\w-])", text, re.IGNORECASE) is not None


def portuguese_problems(text: str) -> list[str]:
    """Reasons ``text`` is not natural Brazilian Portuguese; empty when it passes."""
    problems = [f"Spanish word or phrase: {word}" for word in sorted(SPANISH_ONLY_WORDS) if _contains(text, word)]
    if _SPANISH_PUNCTUATION.search(text):
        problems.append("Spanish punctuation or letter")
    if not any(_contains(text, word) for word in PORTUGUESE_MARKERS) and not _PORTUGUESE_ORTHOGRAPHY.search(text):
        problems.append("no Portuguese marker")
    return problems


def spanish_problems(text: str) -> list[str]:
    """Reasons ``text`` is not Spanish; empty when it passes."""
    problems = [f"Portuguese word: {word}" for word in sorted(PORTUGUESE_ONLY_WORDS) if _contains(text, word)]
    if re.search(r"(ção|ções|ões)\b|[ãõ]", text, re.IGNORECASE):
        problems.append("Portuguese orthography")
    if not any(_contains(text, word) for word in SPANISH_MARKERS):
        problems.append("no Spanish marker")
    return problems
