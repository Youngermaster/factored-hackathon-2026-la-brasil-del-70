"""Figures in customer text: amounts, percentages, durations, dates, times, and plain numbers, in es, pt, and en.

``extract_figures`` finds every figure in a draft so the verifier can check it against clause parameters and
record facts. Numbers accept both conventions (``1.250.000,00`` and ``1,250,000.00``); a lone separator followed
by exactly three digits (``1.250``) is ambiguous, so both readings are kept as candidates and a figure matches
when any candidate does. Currency markers are recorded as written and resolved by the verifier from the account
currency, never assumed. Clause citations, masked numbers, and identifiers that mix letters and digits are not
figures; masked numbers are returned as references.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum


class FigureKind(StrEnum):
    MONEY = "money"
    PERCENT = "percent"
    DURATION = "duration"
    DATE = "date"
    TIME = "time"
    NUMBER = "number"
    REFERENCE = "reference"


class DurationUnit(StrEnum):
    MINUTES = "minutes"
    HOURS = "hours"
    DAYS = "days"
    BUSINESS_DAYS = "business_days"
    MONTHS = "months"
    YEARS = "years"


@dataclass(frozen=True)
class Figure:
    kind: FigureKind
    start: int
    end: int
    values: tuple[Decimal, ...] = ()
    """Candidate numeric values; more than one only for an ambiguous separator."""
    currency_marker: str | None = None
    """``$``, ``PESO``, or an ISO code (``MXN``, ``COP``, ``ARS``, ``USD``, ``BRL``) as written."""
    unit: DurationUnit | None = None
    day: date | None = None
    month_day: tuple[int, int] | None = None
    """Month and day of a date written without a year."""
    time: tuple[int, int] | None = None
    digits: str | None = None
    """The visible digits of a masked number."""


def fold_same_length(text: str) -> str:
    """Casefold and strip accents character by character, keeping every position (``Días`` -> ``dias``)."""
    folded = []
    for character in text:
        decomposed = unicodedata.normalize("NFKD", character.casefold())
        base = "".join(c for c in decomposed if not unicodedata.combining(c))
        folded.append(base if len(base) == 1 else character.lower()[:1] or " ")
    return "".join(folded)


_NUMBER = r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d+)?"


def parse_number(token: str) -> tuple[Decimal, ...]:
    """Candidate values of a numeric token written with either convention."""
    has_dot, has_comma = "." in token, "," in token
    try:
        if has_dot and has_comma:
            decimal_mark = "." if token.rfind(".") > token.rfind(",") else ","
            thousands = "," if decimal_mark == "." else "."
            return (Decimal(token.replace(thousands, "").replace(decimal_mark, ".")),)
        if not (has_dot or has_comma):
            return (Decimal(token),)
        mark = "." if has_dot else ","
        whole, *rest = token.split(mark)
        if len(rest) > 1:
            return (Decimal(token.replace(mark, "")),)
        fraction = rest[0]
        as_decimal = Decimal(f"{whole}.{fraction}")
        if len(fraction) == 3 and 1 <= len(whole) <= 3:
            return (Decimal(f"{whole}{fraction}"), as_decimal)
        return (as_decimal,)
    except InvalidOperation:
        return ()


MONTHS: dict[str, int] = {
    name: number
    for names in (
        "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre",
        "janeiro fevereiro marco abril maio junho julho agosto setembro outubro novembro dezembro",
        "january february march april may june july august september october november december",
    )
    for number, name in enumerate(names.split(), 1)
} | {"setiembre": 9}
_MONTH = "|".join(sorted(MONTHS, key=len, reverse=True))

_CLAUSE_REF = re.compile(r"\[?\b[A-Z]{2,5}-(?:ALL|[A-Z]{2})-\d+(?:\.\d+)*(?:@\d+)?\b\]?")
_MASKED = re.compile(r"[*•xX]{2,}[ -]?(\d{2,6})\b")
_MIXED_IDENTIFIER = re.compile(r"\b[\w-]*(?:[a-z_][\w-]*\d|\d[\w-]*[a-z_])[\w-]*")
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_SLASH_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_TEXT_DATE = re.compile(rf"\b(\d{{1,2}})(?:\s+de)?\s+({_MONTH})\b(?:\s+(?:de|del)?\s*(\d{{4}})\b)?")
_EN_DATE = re.compile(rf"\b({_MONTH})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(\d{{4}})\b)?")
_TIME = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)(?:\s*(?:h|hs|hrs)\b|\b)")
_PERCENT = re.compile(rf"(?<![\w.,])({_NUMBER})\s*(?:%|por\s+ciento\b|por\s+cento\b|percent\b|per\s+cent\b)")
_UNITS = {
    DurationUnit.BUSINESS_DAYS: r"dias?\s+(?:habiles|uteis)|business\s+days?|working\s+days?",
    DurationUnit.DAYS: r"dias?(?:\s+(?:naturales|corridos|calendario|corridos))?|days?",
    DurationUnit.HOURS: r"horas?|hours?",
    DurationUnit.MINUTES: r"minutos?|minutes?",
    DurationUnit.MONTHS: r"meses|mes|months?",
    DurationUnit.YEARS: r"anos?|years?",
}
_DURATION = re.compile(
    rf"(?<![\w.,])({_NUMBER})\s*(?:{'|'.join(f'(?P<{unit.value}>{pattern})' for unit, pattern in _UNITS.items())})\b"
)
_CODE_BEFORE = r"us\$|usd|mxn|cop|ars|brl|r\$|\$"
_CODE_AFTER = (
    r"usd|mxn|cop|ars|brl|pesos?\s+mexicanos|pesos?\s+colombianos|pesos?\s+argentinos|pesos?|"
    r"dolares|dollars?|reais"
)
_MONEY_BEFORE = re.compile(rf"(?<![\w])({_CODE_BEFORE})\s?({_NUMBER})(?![\d])")
_MONEY_AFTER = re.compile(rf"(?<![\w.,])({_NUMBER})\s*({_CODE_AFTER})\b")
_PLAIN = re.compile(rf"(?<![\w.,])({_NUMBER})(?![\w])")
_MARKERS = {
    "us$": "USD",
    "usd": "USD",
    "dolares": "USD",
    "dollar": "USD",
    "dollars": "USD",
    "mxn": "MXN",
    "cop": "COP",
    "ars": "ARS",
    "brl": "BRL",
    "r$": "BRL",
    "reais": "BRL",
    "$": "$",
    "peso": "PESO",
    "pesos": "PESO",
}


def _marker(written: str) -> str:
    words = written.split()
    if len(words) == 2:
        return {"mexicanos": "MXN", "colombianos": "COP", "argentinos": "ARS"}[words[1]]
    return _MARKERS[written]


def _make_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


class _Scanner:
    """Finds figures pattern by pattern, blanking each consumed span so later patterns never see it again."""

    def __init__(self, text: str) -> None:
        self.original = text
        self.work = fold_same_length(text)
        self.figures: list[Figure] = []

    def consume(self, start: int, end: int) -> None:
        self.work = self.work[:start] + " " * (end - start) + self.work[end:]

    def scan(self, pattern: re.Pattern[str], *, original: bool = False) -> list[re.Match[str]]:
        return list(pattern.finditer(self.original if original else self.work))

    def add(self, figure: Figure) -> None:
        self.figures.append(figure)
        self.consume(figure.start, figure.end)


def _dates(scanner: _Scanner) -> None:
    for match in scanner.scan(_ISO_DATE):
        day = _make_date(int(match[1]), int(match[2]), int(match[3]))
        if day is not None:
            scanner.add(Figure(FigureKind.DATE, match.start(), match.end(), day=day))
    for match in scanner.scan(_SLASH_DATE):
        day = _make_date(int(match[3]), int(match[2]), int(match[1]))
        if day is not None:
            scanner.add(Figure(FigureKind.DATE, match.start(), match.end(), day=day))
    for pattern, day_group, month_group in ((_TEXT_DATE, 1, 2), (_EN_DATE, 2, 1)):
        for match in scanner.scan(pattern):
            month, day_number = MONTHS[match[month_group]], int(match[day_group])
            if match[3] is not None:
                day = _make_date(int(match[3]), month, day_number)
                if day is not None:
                    scanner.add(Figure(FigureKind.DATE, match.start(), match.end(), day=day))
            elif _make_date(2024, month, day_number) is not None:
                scanner.add(Figure(FigureKind.DATE, match.start(), match.end(), month_day=(month, day_number)))


def extract_figures(text: str) -> tuple[Figure, ...]:
    """Every figure in ``text``, in order of position."""
    scanner = _Scanner(text)
    for match in scanner.scan(_CLAUSE_REF, original=True):
        scanner.consume(match.start(), match.end())
    for match in scanner.scan(_MASKED, original=True):
        scanner.add(Figure(FigureKind.REFERENCE, match.start(), match.end(), digits=match[1]))
    _dates(scanner)
    for match in scanner.scan(_TIME):
        scanner.add(Figure(FigureKind.TIME, match.start(), match.end(), time=(int(match[1]), int(match[2]))))
    for match in scanner.scan(_MIXED_IDENTIFIER):
        scanner.consume(match.start(), match.end())
    for match in scanner.scan(_PERCENT):
        scanner.add(Figure(FigureKind.PERCENT, match.start(), match.end(), values=parse_number(match[1])))
    for match in scanner.scan(_MONEY_BEFORE):
        values, marker = parse_number(match[2]), _marker(match[1])
        scanner.add(Figure(FigureKind.MONEY, match.start(), match.end(), values=values, currency_marker=marker))
    for match in scanner.scan(_MONEY_AFTER):
        values, marker = parse_number(match[1]), _marker(" ".join(match[2].split()))
        scanner.add(Figure(FigureKind.MONEY, match.start(), match.end(), values=values, currency_marker=marker))
    for match in scanner.scan(_DURATION):
        unit = DurationUnit(match.lastgroup) if match.lastgroup else DurationUnit.DAYS
        scanner.add(Figure(FigureKind.DURATION, match.start(), match.end(), values=parse_number(match[1]), unit=unit))
    for match in scanner.scan(_PLAIN):
        scanner.add(Figure(FigureKind.NUMBER, match.start(), match.end(), values=parse_number(match[1])))
    return tuple(sorted(scanner.figures, key=lambda figure: figure.start))


def citation_markers(text: str) -> tuple[str, ...]:
    """Clause ids written inline, such as ``[DSP-MX-1]`` or ``DSP-MX-1@1``, in order."""
    return tuple(match[0].strip("[]") for match in _CLAUSE_REF.finditer(text))
