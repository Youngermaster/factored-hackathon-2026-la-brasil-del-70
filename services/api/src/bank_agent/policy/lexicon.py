"""Approval wording that no credit text may contain, in any language, even negated.

The synthetic eligibility service gives an indication, never a decision. Credit clauses, the eligibility
messages, and every rendered credit text are checked against these stems and phrases (case and accents ignored),
so a wording such as "this is not an approval" is refused as well: the check needs no exceptions.

Stems are substrings (``aprob`` covers "aprobado", "preaprobado", "pre-aprobado"); phrases are word-bounded
patterns for approval claims without an approval stem ("calificas para el préstamo", "seu crédito foi liberado",
"you qualify for"). Phase 14b added the qualification wording that a naive agent wrote ("estás calificado").
"""

import re
import unicodedata

from bank_agent.domain.locale import Language

APPROVAL_STEMS: dict[Language, tuple[str, ...]] = {
    Language.ES: ("aprob", "otorg", "concedid", "autorizad", "calificad", "cualificad", "precalific"),
    Language.PT: ("aprov", "conced", "outorg", "autorizad", "qualificad", "pre-qualific", "prequalific"),
    Language.EN: ("approv", "grant", "authorized", "authorised", "qualified", "prequalif", "pre-qualif"),
}
ALL_STEMS = tuple(sorted({stem for stems in APPROVAL_STEMS.values() for stem in stems}))

_PRODUCT = r"(?:credito|prestamo|emprestimo|tarjeta|cartao|financiamiento|financiamento|hipoteca|limite)"
APPROVAL_PHRASES: dict[Language, tuple[re.Pattern[str], ...]] = {
    Language.ES: (
        re.compile(r"\b(?:calificas|califica|cualificas|cualifica) (?:para|al|a)\b"),
        re.compile(
            rf"\b(?:habilitad|apt)[oa]s? (?:para|a) (?:(?:el|la|un|una|tu|obtener|recibir|sacar) ){{0,2}}{_PRODUCT}"
        ),
        re.compile(rf"\b{_PRODUCT} (?:\w+ ){{0,3}}(?:ya )?(?:esta|fue|sera|queda) (?:liberad|asegurad)[oa]\b"),
    ),
    Language.PT: (
        re.compile(r"\b(?:voce )?se qualifica (?:para|ao|a)\b"),
        re.compile(
            rf"\b(?:habilitad|apt)[oa]s? (?:para|a) (?:(?:o|a|um|uma|seu|sua|receber|obter|pegar) ){{0,2}}{_PRODUCT}"
        ),
        re.compile(rf"\b{_PRODUCT} (?:\w+ ){{0,3}}(?:ja )?(?:esta|foi|sera|fica) (?:liberad|garantid)[oa]\b"),
    ),
    Language.EN: (
        re.compile(r"\byou (?:qualify|are eligible for (?:the |a |this )?(?:loan|credit|card|approval))\b"),
        re.compile(r"\b(?:loan|credit|card) (?:\w+ ){0,3}(?:is|has been|was|will be) (?:cleared|secured)\b"),
    ),
}
_ALL_PHRASES = tuple(pattern for patterns in APPROVAL_PHRASES.values() for pattern in patterns)


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def approval_terms(text: str) -> tuple[str, ...]:
    """The approval stems found in ``text`` (every language's, in stem order), then the approval phrases found."""
    folded = _fold(text)
    stems = tuple(stem for stem in ALL_STEMS if stem in folded)
    spaced = " ".join(re.findall(r"[\w-]+", folded))
    phrases = tuple(match.group(0) for pattern in _ALL_PHRASES if (match := pattern.search(spaced)))
    return stems + phrases
