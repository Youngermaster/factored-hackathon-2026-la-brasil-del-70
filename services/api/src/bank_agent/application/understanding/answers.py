"""Short answers parsed deterministically: yes or no, an option choice, and a language choice (es and pt).

A reply that contains both a yes and a no marker, or a doubt (``no sé``, ``não sei``), is unclear, and so is
anything without a marker in its first words; the workflow then asks again against the clarification budget.
"""

import re
from collections.abc import Callable, Sequence
from enum import StrEnum

from bank_agent.application.understanding.text import fold, words
from bank_agent.domain.locale import Language


class YesNo(StrEnum):
    YES = "yes"
    NO = "no"
    UNCLEAR = "unclear"


_YES = re.compile(
    r"^(?:si|sim|claro|dale|de una|ok|okay|vale|va|sale|listo|confirmo|confirmado|correcto|correto|adelante|"
    r"hazlo|hacelo|por supuesto|afirmativo|exacto|isso|certo|pode|beleza|com certeza|fechado|positivo|manda ver|"
    r"yes|yep|sure)\b"
)
_NO = re.compile(
    r"^(?:no|nel|nop|nao|nem|para nada|cancelar|cancela|cancelalo|mejor no|todavia no|aun no|negativo|"
    r"melhor nao|ainda nao|de jeito nenhum|nope)\b"
)
_DOUBT = re.compile(r"\b(?:no se|nao sei|tal vez|talvez|quizas|quiza|capaz)\b")
_MAX_WORDS = 8
_ORDINALS = {
    0: r"\b(?:1|primer[oa]?|primeir[oa]|opcion 1|opcao 1)\b|^(?:el |la |o |a |opcion |opcao )?(?:uno|una|um|uma)$",
    1: r"\b(?:2|segund[oa]|opcion 2|opcao 2)\b|^(?:el |la |o |a |opcion |opcao )?(?:dos|dois|duas)$",
    2: r"\b(?:3|tercer[oa]?|terceir[oa]|opcion 3|opcao 3)\b|^(?:el |la |o |a |opcion |opcao )?(?:tres)$",
}
"""Digits and ordinal words count anywhere; a bare number word only as the whole answer, because "uno personal" or
"quiero una hipoteca" uses it as an article (production QA 2026-10-05, CRE-01: "uno personal" picked option 1)."""


def parse_yes_no(text: str) -> YesNo:
    folded = " ".join(words(text))
    if not folded or _DOUBT.search(folded):
        return YesNo.UNCLEAR
    yes = bool(_YES.search(folded))
    no = bool(_NO.search(folded))
    later_no = re.search(r"\b(?:no|nao|cancel\w*)\b", " ".join(folded.split()[1:]))
    if yes and (no or later_no):
        return YesNo.UNCLEAR
    if len(folded.split()) > _MAX_WORDS and not (yes or no):
        return YesNo.UNCLEAR
    if yes:
        return YesNo.YES
    if no:
        return YesNo.NO
    return YesNo.UNCLEAR


def parse_choice[T](text: str, options: Sequence[T], matches: Callable[[str, T], bool] | None = None) -> int | None:
    """The index of the option the customer chose: by ordinal or number, else by one attribute match only."""
    folded = " ".join(words(text))
    picked = [index for index, pattern in _ORDINALS.items() if index < len(options) and re.search(pattern, folded)]
    if len(picked) == 1:
        return picked[0]
    if matches is None:
        return None
    by_attribute = [index for index, option in enumerate(options) if matches(folded, option)]
    return by_attribute[0] if len(by_attribute) == 1 else None


def parse_language_choice(text: str) -> Language | None:
    folded = fold(text)
    spanish = bool(re.search(r"\b(?:espanol|castellano|es)\b|^1$", folded))
    portuguese = bool(re.search(r"\b(?:portugues|pt)\b|^2$", folded))
    if spanish == portuguese:
        return None
    return Language.ES if spanish else Language.PT
