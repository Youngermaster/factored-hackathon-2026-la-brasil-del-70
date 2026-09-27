"""The deterministic descriptor combines the understanding parsers exactly as the model-off UNDERSTAND path does."""

from datetime import date, timedelta
from decimal import Decimal

from bank_agent.application.understanding.descriptor import deterministic_descriptor
from bank_agent.domain.money import Currency
from bank_agent.domain.transaction import TransactionChannel

TODAY = date(2026, 6, 17)


def test_reads_amount_currency_merchant_date_channel_and_card_ending() -> None:
    descriptor = deterministic_descriptor(
        "No reconozco un cargo de 15 lucas en Super Ahorro ayer en la tienda, tarjeta terminada en 4821",
        TODAY,
        frozenset({Currency.ARS}),
    )
    assert descriptor.amount == Decimal(15000)
    assert descriptor.currency_hint is Currency.ARS
    assert descriptor.merchant_text == "super ahorro"
    assert descriptor.resolved_date_range is not None
    assert descriptor.resolved_date_range.start == TODAY - timedelta(days=1)
    assert descriptor.channel_hint is TransactionChannel.POS
    assert descriptor.card_last4_hint == "4821"


def test_unknown_parts_stay_empty_and_several_currencies_leave_the_hint_open() -> None:
    descriptor = deterministic_descriptor("me cobraron 300", TODAY, frozenset({Currency.MXN, Currency.USD}))
    assert descriptor.amount == Decimal(300)
    assert descriptor.currency_hint is None
    assert (descriptor.merchant_text, descriptor.date_expression, descriptor.channel_hint) == (None, None, None)
    assert deterministic_descriptor("hola", TODAY, frozenset()).amount is None


def test_date_interpretations_outside_the_window_are_dropped() -> None:
    inside = deterministic_descriptor("el 03/04", TODAY, frozenset(), earliest=date(2026, 3, 20))
    assert [r.start for r in inside.date_interpretations] == [date(2026, 4, 3)]
    both = deterministic_descriptor("el 03/04", TODAY, frozenset())
    assert both.date_is_ambiguous


def test_an_amount_after_a_named_date_is_not_read_as_its_year() -> None:
    # Regression (phase 10a resolver error analysis): "de 1500 pesos" after "5 de febrero" was taken as the year,
    # so the date moved to 1500 and the amount was lost.
    for text, amount in (
        ("el 5 de febrero de 1500 pesos", Decimal(1500)),
        ("no dia 5 de fevereiro de 12 mil pesos", Decimal(12000)),
        ("el 5 de febrero de 2000 pesos", Decimal(2000)),
    ):
        descriptor = deterministic_descriptor(text, TODAY, frozenset())
        assert descriptor.amount == amount, text
        assert [r.start for r in descriptor.date_interpretations] == [date(2026, 2, 5)], text


def test_a_real_year_after_a_named_date_is_still_a_year() -> None:
    descriptor = deterministic_descriptor("el 5 de febrero de 2025 por 300 pesos", TODAY, frozenset())
    assert descriptor.amount == Decimal(300)
    assert [r.start for r in descriptor.date_interpretations] == [date(2025, 2, 5)]
