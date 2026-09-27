"""Statement periods in Spanish and Portuguese against a fixed reference day (Thursday 2026-06-18)."""

from datetime import date

import pytest

from bank_agent.application.understanding.periods import resolve_period

TODAY = date(2026, 6, 18)


@pytest.mark.parametrize(
    ("text", "start", "end"),
    [
        ("el estado de cuenta del mes pasado", date(2026, 5, 1), date(2026, 5, 31)),
        ("o extrato do mês passado", date(2026, 5, 1), date(2026, 5, 31)),
        ("resumen de mayo", date(2026, 5, 1), date(2026, 5, 31)),
        ("extrato de maio", date(2026, 5, 1), date(2026, 5, 31)),
        ("movimientos de agosto", date(2025, 8, 1), date(2025, 8, 31)),
        ("resumen de junio", date(2026, 6, 1), date(2026, 6, 18)),
        ("los últimos 30 días", date(2026, 5, 20), date(2026, 6, 18)),
        ("os últimos três meses", date(2026, 3, 19), date(2026, 6, 18)),
        ("los últimos seis meses", date(2025, 12, 19), date(2026, 6, 18)),
        ("esta semana", date(2026, 6, 15), date(2026, 6, 18)),
        ("la semana pasada", date(2026, 6, 8), date(2026, 6, 14)),
        ("este mes", date(2026, 6, 1), date(2026, 6, 18)),
    ],
)
def test_periods_resolve_to_ranges(text: str, start: date, end: date) -> None:
    period = resolve_period(text, TODAY)
    assert period is not None
    assert (period.dates.start, period.dates.end) == (start, end)
    assert period.days == (end - start).days + 1


@pytest.mark.parametrize("text", ["mi estado de cuenta", "quero o extrato", "el 03/04", "desde siempre"])
def test_unresolved_or_ambiguous_periods_are_none(text: str) -> None:
    assert resolve_period(text, TODAY) is None
