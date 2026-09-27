"""A small synthetic gold warehouse for the resolver tests (team-made fixture rows, not organizer data).

It follows the serving contract (``GOLD_SCHEMAS``) through the API's own test writer, so the resolver reads it with
the same queries it uses on the real warehouse.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from bank_agent_duckdb import write_table
from bank_ml.common.seeds import rng

MERCHANTS = ("Super Ahorro", "Uber", "Farmacia Salud", "Cine Premium", "Internet Plus", None)
CATEGORIES = {"Super Ahorro": "food", "Uber": "transport", "Farmacia Salud": "health", "Cine Premium": "entertainment"}
COUNTRIES = {"MX": "MXN", "CO": "COP", "AR": "ARS"}
TYPES = ("purchase", "withdrawal", "payment", "transfer", "adjustment")
CHANNELS = ("pos", "app", "web", "atm")
START = datetime(2024, 6, 1, 12)  # noqa: DTZ001 (gold timestamps are naive UTC)
CUSTOMERS = 240
PER_CUSTOMER = 36


def write_synthetic_gold(gold: Path) -> None:
    gold.mkdir(parents=True, exist_ok=True)
    generator = rng("fixture", "resolver-gold")
    customers, transactions, complaints = [], [], []
    for number in range(CUSTOMERS):
        customer = f"CLI-FIX{number:05d}"
        country = ("MX", "CO", "AR")[number % 3]
        currency = COUNTRIES[country]
        customers.append((customer, "Fixture", country, "retail", "active", "id", "0", "0", date(2026, 6, 17)))
        for index in range(PER_CUSTOMER):
            at = START + timedelta(days=generator.randrange(0, 740), minutes=generator.randrange(0, 1440))
            kind = generator.choice(TYPES)
            merchant = generator.choice(MERCHANTS) if kind == "purchase" else None
            amount = Decimal(generator.randrange(500, 900000)) / 100
            transaction_id = f"TRX-FIX{number:05d}{index:03d}"
            transactions.append(
                (transaction_id, customer, f"PRD-FIX{number:05d}", at, at.date(), kind,
                 CATEGORIES.get(merchant or ""), amount, currency, amount, False,
                 generator.choice(CHANNELS), "approved", "00", merchant, None, country, None, False, Decimal(1))
            )  # fmt: skip
            if index == 0 and number % 4 == 0:
                claim = at + timedelta(days=10)
                complaints.append(
                    (f"CMP-FIX{number:05d}", customer, claim, claim.date(), "complaint", "Transactions",
                     "Cargo no reconocido", "app", None, amount, currency, "normal")
                )  # fmt: skip
    write_table(gold, "customers_serving", customers)
    write_table(gold, "transactions_serving", transactions)
    write_table(gold, "complaints_serving", complaints)


@pytest.fixture(scope="session")
def synthetic_gold(tmp_path_factory: pytest.TempPathFactory) -> Path:
    gold = tmp_path_factory.mktemp("gold")
    write_synthetic_gold(gold)
    return gold
