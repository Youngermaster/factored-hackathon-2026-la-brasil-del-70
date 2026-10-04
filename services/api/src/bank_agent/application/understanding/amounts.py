"""Amounts and money slang in Spanish and Portuguese, normalized deterministically.

Multipliers: ``k``, ``mil``, ``luca``/``lucas`` (thousand, Argentina and Chile), ``palo``/``palos`` (million, Argentina
and Colombia), ``millón``/``millones``, ``milhão``/``milhões``. ``varo``/``varos`` and ``pesos`` name the local unit.
Separators follow the text: the last ``.`` or ``,`` followed by exactly three digits is a thousands separator
(``1.250`` and ``1,250`` are 1250), followed by one or two digits it is the decimal mark (``12,50``). A bare ``$``,
``pesos``, or ``varos`` resolves to the account currency later (``resolve_currency``); explicit codes (after the
number, or before it as the web app shows amounts: ``COP 1,015,801.59``) and ``US$`` name a currency. Dates, card
endings, and durations are removed before scanning so their digits are never read as amounts.
"""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from bank_agent.application.understanding.dates import ABBREVIATED_DATE, MONTHS, YEAR
from bank_agent.application.understanding.text import fold
from bank_agent.domain.money import Currency

_MULTIPLIERS: tuple[tuple[str, Decimal], ...] = (
    (r"k", Decimal(1000)),
    (r"mil", Decimal(1000)),
    (r"lucas?", Decimal(1000)),
    (r"palos?", Decimal(1_000_000)),
    (r"millon(?:es)?", Decimal(1_000_000)),
    (r"milh(?:ao|oes)", Decimal(1_000_000)),
)
_MULTIPLIER = "|".join(pattern for pattern, _ in _MULTIPLIERS)
_CODES = {"usd": Currency.USD, "mxn": Currency.MXN, "cop": Currency.COP, "ars": Currency.ARS}
_UNIT = r"pesos?|varos?|reais|dolares|dollars?|usd|mxn|cop|ars|brl"
_AMOUNT = re.compile(
    rf"(?P<symbol>us\$|u\$s|r\$|\$|\b(?:usd|mxn|cop|ars)(?=\s?\d))?"
    rf"\s?(?P<number>\d{{1,3}}(?:[.,]\d{{3}})+(?:[.,]\d{{1,2}})?|\d+(?:[.,]\d{{1,2}})?)"
    rf"(?:\s?(?P<multiplier>{_MULTIPLIER})\b)?(?:\s(?:de\s)?(?P<unit>{_UNIT})\b)?"
)
_COUNTS = {"un": 1, "una": 1, "um": 1, "uma": 1, "dos": 2, "dois": 2, "duas": 2, "tres": 3}
_WORD_AMOUNT = re.compile(
    rf"\b(?P<count>{'|'.join(_COUNTS)})\s(?P<multiplier>lucas?|palos?|millon(?:es)?|milh(?:ao|oes))\b"
)
_NOISE = re.compile(
    r"\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?"
    rf"|\d{{1,2}} de (?:{'|'.join(MONTHS)})(?: de {YEAR})?"
    rf"|{ABBREVIATED_DATE}"
    r"|(?:terminad[ao]|termina|final|finalizad[ao]|acabad[ao]|ending)(?: en| em| in)? \d{4}"
    r"|\d+ (?:dias?|days?|semanas?|meses|mes|horas?|anos?|minutos?)\b"
    r"|\b(?:de|del|en|em|of|in) (?:19|20)\d{2}\b(?! ?(?:pesos|varos|reais|usd|mxn|cop|ars|k\b|mil\b|lucas?))"
    r"|[a-z]+-[a-z0-9-]+"
)


@dataclass(frozen=True)
class AmountMention:
    amount: Decimal
    currency: Currency | None
    """Named explicitly (a code, ``US$``, dollars); ``None`` for a bare ``$``, pesos, varos, or no marker."""
    local_unit: bool
    """A bare ``$``, ``pesos``, or ``varos``: the account currency."""
    has_multiplier: bool
    text: str


def parse_number(raw: str) -> Decimal | None:
    """Parse ``1.250.000,00``, ``1,250.50``, ``1.250``, ``12,5``, or ``800`` as written in es, pt, or en."""
    last = max(raw.rfind("."), raw.rfind(","))
    if last == -1:
        digits = raw
    elif len(raw) - last - 1 == 3:
        digits = raw.replace(".", "").replace(",", "")
    else:
        digits = raw[:last].replace(".", "").replace(",", "") + "." + raw[last + 1 :]
    try:
        return Decimal(digits)
    except InvalidOperation:
        return None


def _multiplier(word: str | None) -> Decimal:
    if not word:
        return Decimal(1)
    for pattern, value in _MULTIPLIERS:
        if re.fullmatch(pattern, word):
            return value
    return Decimal(1)


def _currency(symbol: str | None, unit: str | None) -> tuple[Currency | None, bool]:
    unit = unit or ""
    if symbol in {"us$", "u$s"} or unit in {"dolares", "dollar", "dollars"}:
        return Currency.USD, False
    if unit in _CODES:
        return _CODES[unit], False
    if symbol in _CODES:
        return _CODES[symbol], False
    return None, symbol == "$" or unit.startswith(("peso", "varo"))


def parse_amounts(text: str) -> list[AmountMention]:
    """Every amount mentioned in ``text``, in order."""
    folded = _NOISE.sub(" ", fold(text))
    mentions: list[AmountMention] = []
    for match in _AMOUNT.finditer(folded):
        number = parse_number(match["number"])
        if number is None:
            continue
        multiplier = _multiplier(match["multiplier"])
        currency, local = _currency(match["symbol"], match["unit"])
        mentions.append(
            AmountMention(number * multiplier, currency, local, match["multiplier"] is not None, match[0].strip())
        )
    for match in _WORD_AMOUNT.finditer(folded):
        slang = match["multiplier"].startswith(("luca", "palo"))
        amount = _COUNTS[match["count"]] * _multiplier(match["multiplier"])
        mentions.append(AmountMention(amount, None, slang, True, match[0]))
    return mentions


def best_amount(text: str) -> AmountMention | None:
    """The first amount with a currency marker or multiplier, else the first amount."""
    mentions = parse_amounts(text)
    marked = [m for m in mentions if m.currency is not None or m.local_unit or m.has_multiplier]
    chosen = marked or mentions
    return chosen[0] if chosen else None


def resolve_currency(mention: AmountMention, account_currencies: frozenset[Currency]) -> Currency | None:
    """The mention's currency: explicit, else the account currency when the customer's products share one."""
    if mention.currency is not None:
        return mention.currency
    if len(account_currencies) == 1:
        return next(iter(account_currencies))
    return None
