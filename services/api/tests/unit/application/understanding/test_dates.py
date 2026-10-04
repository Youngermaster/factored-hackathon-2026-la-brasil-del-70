"""Relative and explicit date table for Spanish and Portuguese with a fixed reference day (Thursday 2026-06-18)."""

from datetime import date

import pytest

from bank_agent.application.understanding.dates import narrow, resolve_dates
from bank_agent.domain.intelligence import DateRange

TODAY = date(2026, 6, 18)


def day(value: str) -> tuple[DateRange, ...]:
    parsed = date.fromisoformat(value)
    return (DateRange(start=parsed, end=parsed),)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("fue ayer", day("2026-06-17")),
        ("foi ontem", day("2026-06-17")),
        ("anteayer", day("2026-06-16")),
        ("antier en la noche", day("2026-06-16")),
        ("anteontem", day("2026-06-16")),
        ("hoy temprano", day("2026-06-18")),
        ("hoje", day("2026-06-18")),
        ("hace 3 días", day("2026-06-15")),
        ("há 2 dias", day("2026-06-16")),
        ("faz dois dias", day("2026-06-16")),
        ("el martes pasado", day("2026-06-16")),
        ("na terça-feira passada", day("2026-06-16")),
        ("el jueves", day("2026-06-11")),
        ("el 7 de junio", day("2026-06-07")),
        ("em 7 de junho de 2026", day("2026-06-07")),
        ("el 20 de diciembre", day("2025-12-20")),
        ("el 15/06", day("2026-06-15")),
        # The medium dates the web app shows in statements (es-MX and es-AR, pt-BR): abbreviated months, with a year.
        ("el cargo del 23 abr 2026", day("2026-04-23")),
        ("a cobrança de 23 de abr. de 2026", day("2026-04-23")),
        ("el 2 dic 2025", day("2025-12-02")),
        ("em 9 de set. de 2025", day("2025-09-09")),
        ("la semana pasada", (DateRange(start=date(2026, 6, 8), end=date(2026, 6, 14)),)),
        ("semana passada", (DateRange(start=date(2026, 6, 8), end=date(2026, 6, 14)),)),
        ("el mes pasado", (DateRange(start=date(2026, 5, 1), end=date(2026, 5, 31)),)),
        ("mês passado", (DateRange(start=date(2026, 5, 1), end=date(2026, 5, 31)),)),
        ("este mes", (DateRange(start=date(2026, 6, 1), end=TODAY),)),
    ],
)
def test_resolves_dates(text: str, expected: tuple[DateRange, ...]) -> None:
    mention = resolve_dates(text, TODAY)
    assert mention is not None
    assert mention.interpretations == expected


def test_day_and_month_order_is_ambiguous_when_both_could_be_a_month() -> None:
    mention = resolve_dates("una compra el 03/04", TODAY)
    assert mention is not None
    assert mention.interpretations == day("2026-04-03") + day("2026-03-04")
    assert resolve_dates("el 04/04", TODAY) is not None


def test_context_narrows_the_ambiguity() -> None:
    mention = resolve_dates("el 05/06", TODAY)
    assert mention is not None
    assert len(mention.interpretations) == 2
    assert narrow(mention.interpretations, date(2026, 5, 20), TODAY) == day("2026-06-05")


def test_no_date_and_an_impossible_date() -> None:
    assert resolve_dates("no reconozco un cargo", TODAY) is None
    assert resolve_dates("el 31/02", TODAY) is None
