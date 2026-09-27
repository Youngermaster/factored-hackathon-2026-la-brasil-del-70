"""Approval wording that no credit text may contain, in any language, even negated.

The synthetic eligibility service gives an indication, never a decision. Credit clauses, the eligibility
messages, and every rendered credit text are checked against these stems (case and accents ignored), so a
wording such as "this is not an approval" is refused as well: the check needs no exceptions.
"""

import unicodedata

from bank_agent.domain.locale import Language

APPROVAL_STEMS: dict[Language, tuple[str, ...]] = {
    Language.ES: ("aprob", "otorg", "concedid", "autorizad"),
    Language.PT: ("aprov", "conced", "outorg", "autorizad"),
    Language.EN: ("approv", "grant", "authorized", "authorised"),
}
ALL_STEMS = tuple(sorted({stem for stems in APPROVAL_STEMS.values() for stem in stems}))


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def approval_terms(text: str) -> tuple[str, ...]:
    """The approval stems found in ``text``, checking every language's stems, in stem order."""
    folded = _fold(text)
    return tuple(stem for stem in ALL_STEMS if stem in folded)
