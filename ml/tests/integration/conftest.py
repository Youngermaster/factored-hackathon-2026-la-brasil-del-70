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


RISK_CUSTOMERS = 2400
SNAPSHOT = date(2026, 6, 17)
DPD_VALUES = (0, 0, 0, 0, 0, 0, 15, 30, 60, 90)
BALANCE_AS_OF = datetime(2026, 6, 18, 5, 59, 59)  # noqa: DTZ001 (gold timestamps are naive UTC)


def write_risk_gold(gold: Path) -> None:
    """Credit profiles, products, and customers where delinquency is per product (team-made fixture rows)."""
    gold.mkdir(parents=True, exist_ok=True)
    generator = rng("fixture", "risk-gold")
    customers, profiles, products = [], [], []
    for number in range(RISK_CUSTOMERS):
        customer = f"CLI-RSK{number:05d}"
        country = ("MX", "CO", "AR")[number % 3]
        segment = ("basic", "plus", "premium", "student")[number % 4]
        customers.append((customer, "Fixture", country, segment, "active", "id", "0", "0", SNAPSHOT))
        count = generator.choice((0, 1, 1, 1, 2, 2, 3, 4))
        worst: int | None = None
        for index in range(count):
            dpd = None if generator.random() < 0.02 else generator.choice(DPD_VALUES)
            worst = dpd if worst is None or (dpd is not None and dpd > worst) else worst
            products.append(
                (f"PRD-RSK{number:05d}{index}", customer, ("credit_card", "personal_loan", "mortgage")[index % 3],
                 "active", "1234", COUNTRIES[country], Decimal(100), Decimal(1000), Decimal("0.3"), date(2023, 1, 1),
                 None, dpd, BALANCE_AS_OF, False, index % 3 == 0, True, SNAPSHOT)
            )  # fmt: skip
        products.append(
            (f"PRD-RSK{number:05d}C", customer, "credit_card", "closed", "9999", COUNTRIES[country], Decimal(0),
             Decimal(500), Decimal("0.3"), date(2022, 1, 1), None, 180, BALANCE_AS_OF, False, True, True, SNAPSHOT)
        )  # fmt: skip
        score = None if generator.random() < 0.1 else generator.randrange(420, 850)
        utilization = None if generator.random() < 0.3 else Decimal(generator.randrange(0, 12000)) / 10000
        income = Decimal(generator.randrange(10000, 90000))
        profiles.append((customer, score, income, COUNTRIES[country], generator.randrange(0, 96), count, worst,
                         None, None, utilization, SNAPSHOT))  # fmt: skip
    write_table(gold, "customers_serving", customers)
    write_table(gold, "credit_profiles_serving", profiles)
    write_table(gold, "products_serving", products)


@pytest.fixture(scope="session")
def risk_gold(tmp_path_factory: pytest.TempPathFactory) -> Path:
    gold = tmp_path_factory.mktemp("risk-gold")
    write_risk_gold(gold)
    return gold
