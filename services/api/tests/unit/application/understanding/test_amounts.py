"""Slang and amount normalization table for Spanish and Portuguese (team-written fixture sentences)."""

from decimal import Decimal

import pytest

from bank_agent.application.understanding.amounts import best_amount, parse_amounts, parse_number, resolve_currency
from bank_agent.domain.money import Currency


@pytest.mark.parametrize(
    ("text", "amount", "currency", "local"),
    [
        ("Che, me cobraron 15 lucas en el super", "15000", None, False),
        ("una luca", "1000", None, True),
        ("me cobraron 2 palos", "2000000", None, False),
        ("un palo", "1000000", None, True),
        ("20 mil varos", "20000", None, True),
        ("1.5k", "1500", None, False),
        ("un cargo de $1,250.00 de ayer", "1250.00", None, True),
        ("un cargo de 1.250.000,50 pesos", "1250000.50", None, True),
        ("cobraram R$ 350,90 ontem", "350.90", None, False),
        ("compra de 12,50 USD hace 3 días", "12.50", Currency.USD, False),
        ("US$ 40", "40", Currency.USD, False),
        ("3 millones de pesos", "3000000", None, True),
        ("dois milhões", "2000000", None, False),
        ("me cobraron 2000 en el super", "2000", None, False),
    ],
)
def test_normalizes_amounts_and_slang(text: str, amount: str, currency: Currency | None, local: bool) -> None:
    mention = best_amount(text)
    assert mention is not None
    assert mention.amount == Decimal(amount)
    assert (mention.currency, mention.local_unit) == (currency, local)


@pytest.mark.parametrize(
    "text",
    [
        "el 03/04 en la tienda",
        "terminada en 1234",
        "hace 3 días",
        "el 7 de junio de 2026",
        "mi transacción TRX-01Z3FVAVD6QZ3TAEVVJS",
        "pasó en 2026",
    ],
)
def test_dates_card_endings_durations_and_ids_are_not_amounts(text: str) -> None:
    assert parse_amounts(text) == []


def test_number_separators_follow_the_digits_after_the_last_mark() -> None:
    assert parse_number("1.250") == Decimal(1250)
    assert parse_number("1,250") == Decimal(1250)
    assert parse_number("12,5") == Decimal("12.5")
    assert parse_number("1,250.75") == Decimal("1250.75")


def test_a_bare_dollar_resolves_to_the_single_account_currency() -> None:
    mention = best_amount("$500")
    assert mention is not None
    assert resolve_currency(mention, frozenset({Currency.ARS})) is Currency.ARS
    assert resolve_currency(mention, frozenset({Currency.ARS, Currency.USD})) is None
    explicit = best_amount("500 USD")
    assert explicit is not None
    assert resolve_currency(explicit, frozenset({Currency.ARS})) is Currency.USD


def test_a_marked_amount_wins_over_a_plain_number() -> None:
    mention = best_amount("la compra 2 de 300 pesos")
    assert mention is not None
    assert mention.amount == Decimal(300)
