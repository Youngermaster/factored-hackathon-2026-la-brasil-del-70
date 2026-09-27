"""Relative and explicit dates in Spanish and Portuguese, resolved against a reference day from the ``Clock``.

The reference day is today in the customer's time zone. Rules, first match wins:

- ``anteayer``/``antier``/``anteontem``: two days back; ``ayer``/``ontem``: one; ``hoy``/``hoje``: today.
- ``hace N días``/``há N dias``/``faz N dias``: N days back (``un``, ``dos``, ``tres``, ``um``, ``dois``, ``três`` too).
- A weekday with or without ``pasado``/``passado(a)``: the most recent such day before today (7 days back when
  today is that weekday).
- ``la semana pasada``/``semana passada``: the previous Monday to Sunday; ``esta semana``: Monday to today.
- ``el mes pasado``/``mês passado``: the previous calendar month; ``este mes``: the first of the month to today.
- ``7 de junio`` (``de 2026`` optional): that day, in the most recent year that is not in the future.
- ``dd/mm`` or ``dd/mm/yyyy``: both orders when both parts could be a month and they differ (``03/04``), so the
  workflow asks unless context drops one; otherwise the one valid order.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta

from bank_agent.application.understanding.text import fold
from bank_agent.domain.intelligence import DateRange

MONTHS = {
    "enero": 1, "janeiro": 1, "febrero": 2, "fevereiro": 2, "marzo": 3, "marco": 3, "abril": 4, "mayo": 5,
    "maio": 5, "junio": 6, "junho": 6, "julio": 7, "julho": 7, "agosto": 8, "septiembre": 9, "setiembre": 9,
    "setembro": 9, "octubre": 10, "outubro": 10, "noviembre": 11, "novembro": 11, "diciembre": 12, "dezembro": 12,
}  # fmt: skip
WEEKDAYS = {
    "lunes": 0, "segunda": 0, "martes": 1, "terca": 1, "miercoles": 2, "quarta": 2, "jueves": 3, "quinta": 3,
    "viernes": 4, "sexta": 4, "sabado": 5, "domingo": 6,
}  # fmt: skip
_SMALL = {"un": 1, "una": 1, "um": 1, "uma": 1, "dos": 2, "dois": 2, "duas": 2, "tres": 3, "cuatro": 4, "quatro": 4}
_DAYS_AGO = re.compile(r"\b(?:hace|ha|faz)\s(?P<n>\d{1,2}|[a-z]+)\sdias?\b")
_WEEKDAY = re.compile(rf"\b(?P<day>{'|'.join(WEEKDAYS)})(?:-feira)?\b")
_NAMED = re.compile(rf"\b(?P<day>\d{{1,2}}) de (?P<month>{'|'.join(MONTHS)})(?: de (?P<year>\d{{4}}))?\b")
_NUMERIC = re.compile(r"\b(?P<a>\d{1,2})[/-](?P<b>\d{1,2})(?:[/-](?P<year>\d{2,4}))?\b")


@dataclass(frozen=True)
class DateMention:
    expression: str
    interpretations: tuple[DateRange, ...]


def _day(value: date) -> tuple[DateRange, ...]:
    return (DateRange(start=value, end=value),)


def _safe(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _latest_not_future(month: int, day: int, today: date, year: int | None) -> date | None:
    if year is not None:
        return _safe(year + 2000 if year < 100 else year, month, day)
    candidate = _safe(today.year, month, day)
    if candidate is not None and candidate > today:
        candidate = _safe(today.year - 1, month, day)
    return candidate


def _relative(folded: str, today: date) -> DateMention | None:
    for pattern, back in (
        (r"\b(?:anteayer|antier|antes de ayer|anteontem)\b", 2),
        (r"\b(?:ayer|ontem)\b", 1),
        (r"\b(?:hoy|hoje)\b", 0),
    ):
        match = re.search(pattern, folded)
        if match:
            return DateMention(match[0], _day(today - timedelta(days=back)))
    match = _DAYS_AGO.search(folded)
    if match:
        raw = match["n"]
        count = int(raw) if raw.isdigit() else _SMALL.get(raw)
        if count is not None:
            return DateMention(match[0], _day(today - timedelta(days=count)))
    return None


def _periods(folded: str, today: date) -> DateMention | None:
    monday = today - timedelta(days=today.weekday())
    if match := re.search(r"\bsemana pasad[ao]\b|\bsemana passada\b", folded):
        start = monday - timedelta(days=7)
        return DateMention(match[0], (DateRange(start=start, end=start + timedelta(days=6)),))
    if match := re.search(r"\b(?:esta|essa|nesta) semana\b", folded):
        return DateMention(match[0], (DateRange(start=monday, end=today),))
    if match := re.search(r"\bmes pasado\b|\bmes passado\b", folded):
        end = today.replace(day=1) - timedelta(days=1)
        return DateMention(match[0], (DateRange(start=end.replace(day=1), end=end),))
    if match := re.search(r"\b(?:este|esse|neste) mes\b", folded):
        return DateMention(match[0], (DateRange(start=today.replace(day=1), end=today),))
    if match := _WEEKDAY.search(folded):
        back = (today.weekday() - WEEKDAYS[match["day"]]) % 7 or 7
        return DateMention(match[0], _day(today - timedelta(days=back)))
    return None


def _explicit(folded: str, today: date) -> DateMention | None:
    if match := _NAMED.search(folded):
        year = int(match["year"]) if match["year"] else None
        value = _latest_not_future(MONTHS[match["month"]], int(match["day"]), today, year)
        return DateMention(match[0], _day(value)) if value is not None else None
    if match := _NUMERIC.search(folded):
        first, second = int(match["a"]), int(match["b"])
        year = int(match["year"]) if match["year"] else None
        orders = [(second, first)] if first == second else [(second, first), (first, second)]
        found = [_latest_not_future(month, day, today, year) for month, day in orders if 1 <= month <= 12]
        unique = tuple(dict.fromkeys(value for value in found if value is not None))
        return DateMention(match[0], tuple(DateRange(start=v, end=v) for v in unique)) if unique else None
    return None


def resolve_dates(text: str, today: date) -> DateMention | None:
    """The first date expression in ``text`` with its interpretations, or ``None``."""
    folded = fold(text)
    return _relative(folded, today) or _explicit(folded, today) or _periods(folded, today)


def narrow(interpretations: tuple[DateRange, ...], earliest: date, latest: date) -> tuple[DateRange, ...]:
    """Drop interpretations entirely outside ``earliest``..``latest`` (the future, or before the dispute window)."""
    return tuple(r for r in interpretations if r.end >= earliest and r.start <= latest)
