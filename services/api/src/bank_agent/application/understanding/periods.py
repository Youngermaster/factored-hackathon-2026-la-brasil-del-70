"""Statement periods in Spanish and Portuguese, resolved against a reference day from the ``Clock``.

First match wins:

- the relative and explicit expressions of ``dates.resolve_dates`` (``el mes pasado``, ``mês passado``, ``esta
  semana``, ``la semana pasada``, ``este mes``, a single day), when they give exactly one range;
- ``últimos N días``/``últimos N meses`` (``últimos 3 meses``, ``los últimos seis meses``, ``últimos 90 dias``):
  the N days or calendar months that end today;
- a month name on its own (``mayo``, ``de maio``, ``agosto de 2025``): that whole month, in the most recent year that
  is not in the future.

Anything else is unresolved, and the workflow asks. The period is never longer than asked and is not clipped here:
the ``ACC.statement_period_within_limit`` rule decides whether it is too long.
"""

import re
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta

from bank_agent.application.understanding.dates import MONTHS, resolve_dates
from bank_agent.application.understanding.text import fold
from bank_agent.domain.intelligence import DateRange

_NUMBERS = {
    "un": 1, "una": 1, "um": 1, "uma": 1, "dos": 2, "dois": 2, "duas": 2, "tres": 3, "cuatro": 4, "quatro": 4,
    "cinco": 5, "seis": 6, "siete": 7, "sete": 7, "ocho": 8, "oito": 8, "nueve": 9, "nove": 9, "diez": 10, "dez": 10,
    "once": 11, "onze": 11, "doce": 12, "doze": 12,
}  # fmt: skip
_LAST = re.compile(r"\bultim[oa]s\s(?P<n>\d{1,3}|[a-z]+)\s(?P<unit>dias?|mes(?:es)?)\b")
_MONTH = re.compile(rf"\b(?P<month>{'|'.join(sorted(MONTHS, key=len, reverse=True))})\b(?: de (?P<year>\d{{4}}))?")


@dataclass(frozen=True)
class Period:
    expression: str
    dates: DateRange

    @property
    def days(self) -> int:
        return (self.dates.end - self.dates.start).days + 1


def _months_back(today: date, months: int) -> date:
    year, month = divmod(today.month - 1 - months, 12)
    target_year, target_month = today.year + year, month + 1
    day = min(today.day, monthrange(target_year, target_month)[1])
    return date(target_year, target_month, day) + timedelta(days=1)


def _last(folded: str, today: date) -> Period | None:
    match = _LAST.search(folded)
    if match is None:
        return None
    raw = match["n"]
    count = int(raw) if raw.isdigit() else _NUMBERS.get(raw)
    if not count:
        return None
    days = match["unit"].startswith("dia")
    start = today - timedelta(days=count - 1) if days else _months_back(today, count)
    return Period(match[0], DateRange(start=start, end=today))


def _month(folded: str, today: date) -> Period | None:
    match = _MONTH.search(folded)
    if match is None:
        return None
    month = MONTHS[match["month"]]
    year = int(match["year"]) if match["year"] else (today.year if month <= today.month else today.year - 1)
    end = date(year, month, monthrange(year, month)[1])
    if date(year, month, 1) > today:
        return None
    return Period(match[0], DateRange(start=date(year, month, 1), end=min(end, today)))


def resolve_period(text: str, today: date) -> Period | None:
    """The statement period ``text`` names, or ``None`` when it names none (or more than one reading)."""
    folded = fold(text)
    last = _last(folded, today)
    if last is not None:
        return last
    mention = resolve_dates(text, today)
    if mention is not None and len(mention.interpretations) == 1:
        return Period(mention.expression, mention.interpretations[0])
    return _month(folded, today)
