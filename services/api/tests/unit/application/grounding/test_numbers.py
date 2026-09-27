"""Normalization tables for figures written in Spanish, Portuguese, and English."""

from datetime import date
from decimal import Decimal

import pytest

from bank_agent.application.grounding.numbers import (
    DurationUnit,
    FigureKind,
    citation_markers,
    extract_figures,
    fold_same_length,
    parse_number,
)


@pytest.mark.parametrize(
    ("token", "values"),
    [
        ("1.250.000,00", ("1250000.00",)),
        ("1,250,000.00", ("1250000.00",)),
        ("1250000", ("1250000",)),
        ("1.250.000", ("1250000",)),
        ("1,250,000", ("1250000",)),
        ("10.000,50", ("10000.50",)),
        ("35,5", ("35.5",)),
        ("35.5", ("35.5",)),
        ("0,12", ("0.12",)),
        ("1.250", ("1250", "1.250")),
        ("1,250", ("1250", "1.250")),
        ("12345,678", ("12345.678",)),
    ],
)
def test_numbers_in_either_convention(token: str, values: tuple[str, ...]) -> None:
    assert parse_number(token) == tuple(Decimal(value) for value in values)


def only(text: str, kind: FigureKind) -> list[tuple[str, tuple[Decimal, ...]]]:
    return [(text[f.start : f.end], f.values) for f in extract_figures(text) if f.kind is kind]


@pytest.mark.parametrize(
    ("text", "unit", "value"),
    [
        ("tienes 60 días para reclamar", DurationUnit.DAYS, "60"),
        ("você tem 60 dias", DurationUnit.DAYS, "60"),
        ("within 60 days", DurationUnit.DAYS, "60"),
        ("90 días naturales", DurationUnit.DAYS, "90"),
        ("30 días corridos", DurationUnit.DAYS, "30"),
        ("15 días calendario", DurationUnit.DAYS, "15"),
        ("5 días hábiles", DurationUnit.BUSINESS_DAYS, "5"),
        ("5 dias úteis", DurationUnit.BUSINESS_DAYS, "5"),
        ("24 horas", DurationUnit.HOURS, "24"),
        ("48 hours", DurationUnit.HOURS, "48"),
        ("5 minutos", DurationUnit.MINUTES, "5"),
        ("12 meses", DurationUnit.MONTHS, "12"),
        ("18 months", DurationUnit.MONTHS, "18"),
        ("2 años", DurationUnit.YEARS, "2"),
    ],
)
def test_durations_in_es_pt_and_en(text: str, unit: DurationUnit, value: str) -> None:
    (figure,) = [f for f in extract_figures(text) if f.kind is FigureKind.DURATION]
    assert (figure.unit, figure.values) == (unit, (Decimal(value),))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("el 17 de junio de 2026", date(2026, 6, 17)),
        ("em 17 de junho de 2026", date(2026, 6, 17)),
        ("17 de março de 2026", date(2026, 3, 17)),
        ("1 de setiembre del 2026", date(2026, 9, 1)),
        ("on June 17, 2026", date(2026, 6, 17)),
        ("17 June 2026", date(2026, 6, 17)),
        ("2026-06-17", date(2026, 6, 17)),
        ("17/06/2026", date(2026, 6, 17)),
    ],
)
def test_dates_with_month_names_in_es_pt_and_en(text: str, expected: date) -> None:
    (figure,) = [f for f in extract_figures(text) if f.kind is FigureKind.DATE]
    assert figure.day == expected


def test_a_date_without_a_year_keeps_month_and_day_and_invalid_dates_are_numbers() -> None:
    (figure,) = extract_figures("hasta el 5 de mayo")
    assert (figure.kind, figure.month_day) == (FigureKind.DATE, (5, 5))
    kinds = [f.kind for f in extract_figures("31/02/2026")]
    assert FigureKind.DATE not in kinds


@pytest.mark.parametrize(
    ("text", "marker", "value"),
    [
        ("$1.250.000,00", "$", "1250000.00"),
        ("$ 1,250.00", "$", "1250.00"),
        ("US$ 50", "USD", "50"),
        ("R$ 1.250,00", "BRL", "1250.00"),
        ("10,000.00 MXN", "MXN", "10000.00"),
        ("2.000.000,00 COP", "COP", "2000000.00"),
        ("600.000,00 ARS", "ARS", "600000.00"),
        ("2.000.000 pesos colombianos", "COP", "2000000"),
        ("500 pesos", "PESO", "500"),
        ("50 dólares", "USD", "50"),
        ("50 reais", "BRL", "50"),
    ],
)
def test_amounts_keep_their_currency_marker_as_written(text: str, marker: str, value: str) -> None:
    (figure,) = extract_figures(text)
    assert figure.kind is FigureKind.MONEY
    assert figure.currency_marker == marker
    assert Decimal(value) in figure.values


@pytest.mark.parametrize("text", ["35 %", "35%", "35 por ciento", "35 por cento", "35 percent"])
def test_percentages(text: str) -> None:
    assert only(text, FigureKind.PERCENT) == [(text, (Decimal(35),))]


def test_citations_masked_numbers_identifiers_and_times() -> None:
    text = "Ver [DSP-MX-1@1] y ELG-MX-1.2; tarjeta ****1234, caso CASE-000123 o case_01J8, a las 10:30 h."
    figures = extract_figures(text)
    assert [f.kind for f in figures] == [FigureKind.REFERENCE, FigureKind.TIME]
    assert figures[0].digits == "1234"
    assert figures[1].time == (10, 30)
    assert citation_markers(text) == ("DSP-MX-1@1", "ELG-MX-1.2")


def test_folding_keeps_positions() -> None:
    text = "Días hábiles: CARTÃO ﬁn"
    folded = fold_same_length(text)
    assert len(folded) == len(text)
    assert folded.startswith("dias habiles: cartao")
