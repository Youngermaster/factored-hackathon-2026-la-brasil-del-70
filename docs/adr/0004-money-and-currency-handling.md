# 0004: Money and currency handling

- Status: accepted
- Date: 2026-09-26

## Context

The dataset stores amounts as `DECIMAL(15,2)` in four currencies (MXN, COP, ARS, USD), with a nullable `amount_usd` that must sometimes be recomputed from daily exchange rates. Disputes compare amounts against policy limits (for example an automatic intake limit in USD), grounding checks that every amount in a response matches a record or a clause parameter, and handoffs and execution records carry amounts to agents and auditors. Binary floating point cannot represent most decimal amounts exactly, and silently mixing currencies would produce materially incorrect outcomes, which the brief counts as unsafe.

## Considered options

1. **Floats with rounding at display time.** Simple, but `0.1 + 0.2 != 0.3`, limit checks at the boundary become unreliable, and JSON numbers lose precision in some consumers.
2. **Integer minor units** (cents). Exact and fast, but every currency needs a fixed scale, exchange-rate products need extra digits, and the dataset's decimal columns need conversion everywhere.
3. **A `Money` value object with a `Decimal` amount and an explicit currency**, exact arithmetic, and explicit conversion and rounding.

## Decision

Option 3, implemented in `bank_agent/domain/money.py`:

- `Money(amount: Decimal, currency: Currency)`. Floats, booleans, NaN, and infinities are rejected at construction.
- Addition, subtraction, and comparison are allowed only within one currency; otherwise `CurrencyMismatchError`. Multiplication accepts `int` or `Decimal` only.
- Arithmetic runs in a decimal context with precision 34 that traps `Inexact`: a result that cannot be represented exactly raises `MoneyPrecisionError` instead of being rounded. Within the dataset range, sums are exact, so addition is associative and commutative (proved by Hypothesis tests).
- Conversion happens only through `ExchangeRate(source, target, rate, as_of).convert(money)`, which returns an unrounded amount in the target currency.
- Rounding happens only when `rounded()` is called: banker's rounding (round half to even) to the currency's ISO 4217 minor units, which are 2 for all four currencies. `0.125` becomes `0.12` and `0.135` becomes `0.14`. Banker's rounding avoids the upward bias of round-half-up when many rounded values are summed.
- JSON carries amounts as strings: `{"amount": "12.50", "currency": "MXN"}`. Policy clause parameters that are amounts use the same object form, so no amount is ever parsed as a float from YAML.

## Consequences

- Currency mistakes fail loudly at the point of the mistake instead of producing a plausible wrong number.
- Every amount has to be constructed deliberately (`Money.of("12.50", Currency.MXN)`), and callers must decide when to round, which is more verbose than floats.
- Display precision (for example showing COP without decimals) is a frontend formatting concern handled with `Intl`, not a domain rule.
- The `Inexact` trap turns a precision problem into an error; with amounts bounded by `DECIMAL(15,2)` and rates by `DECIMAL(12,6)`, results stay far inside 34 digits.
