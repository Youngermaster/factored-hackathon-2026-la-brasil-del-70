"""Silver labels: complaints matched to the complainant's own transactions, a verification sheet, and a secondary
evaluation.

A complaint in ``Transactions`` or ``Fees`` with a claimed amount matches a transaction of the same customer in the
same currency whose amount is within 1% of the claim and which occurred in the 60 days before the complaint.
``affected_product_id`` is never used (it always names another customer's product, BACKLOG), so "product" in the
prompt's matching rule cannot be applied. A unique match is a silver label. Precision is unknown until the
100-item sheet (``data/labeling/resolver_silver_sample.csv``, gitignored because it holds organizer records) is
verified; until then it is reported as pending. The evaluation is secondary and partly circular: the descriptor
carries the claimed amount, which is also the matching key.
"""

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from bank_agent.domain.intelligence import DateRange, TransactionDescriptor
from bank_agent.domain.locale import Country
from bank_agent.domain.money import Currency
from bank_agent.domain.transaction import Transaction
from bank_ml.common.hashing import salted_order
from bank_ml.resolver.dataset import Query
from bank_ml.resolver.gold import GoldReader

CATEGORIES = ("Transactions", "Fees")
TOLERANCE = Decimal("0.01")
WINDOW_DAYS = 60
SHEET_SIZE = 100
EVALUATION_SIZE = 1000
SALT = "resolver-silver-v1"
SHEET_COLUMNS = (
    "complaint_id", "category", "claimed_amount", "currency", "created_at", "transaction_id", "transaction_amount",
    "transaction_at", "merchant_name", "verified_match", "verifier", "notes",
)  # fmt: skip


@dataclass(frozen=True)
class SilverMatch:
    complaint_id: str
    category: str
    customer_id: str
    created_at: datetime
    claimed: Decimal
    currency: Currency
    matches: tuple[Transaction, ...]


def match(reader: GoldReader) -> list[SilverMatch]:
    complaints = [c for c in reader.complaints(CATEGORIES) if c.currency in Currency.__members__]
    transactions = reader.transactions_of(sorted({c.customer_id for c in complaints}))
    found: list[SilverMatch] = []
    for complaint in complaints:
        created = complaint.created_at.replace(tzinfo=UTC)  # type: ignore[attr-defined]
        claimed = Decimal(str(complaint.claimed_amount))
        currency = Currency(complaint.currency)
        start = created - timedelta(days=WINDOW_DAYS)
        matches = tuple(
            txn
            for txn in transactions.get(complaint.customer_id, [])
            if txn.amount.currency is currency
            and start <= txn.occurred_at <= created
            and abs(txn.amount.amount - claimed) <= claimed * TOLERANCE
        )
        found.append(
            SilverMatch(
                complaint.complaint_id, complaint.category, complaint.customer_id, created, claimed, currency, matches
            )
        )
    return found


def counts(matches: Sequence[SilverMatch]) -> dict[str, int]:
    return {
        "complaints_with_claimed_amount": len(matches),
        "with_any_match": sum(1 for m in matches if m.matches),
        "unique_match": sum(1 for m in matches if len(m.matches) == 1),
        "several_matches": sum(1 for m in matches if len(m.matches) > 1),
    }


def unique(matches: Sequence[SilverMatch]) -> list[SilverMatch]:
    return sorted((m for m in matches if len(m.matches) == 1), key=lambda m: salted_order(SALT, m.complaint_id))


def export_sheet(matches: Sequence[SilverMatch], path: Path) -> str:
    """Write the verification sheet unless a verified one exists."""
    if path.is_file():
        with path.open(encoding="utf-8") as stream:
            if any(row.get("verified_match", "").strip() for row in csv.DictReader(stream)):
                return "kept"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        for silver in unique(matches)[:SHEET_SIZE]:
            txn = silver.matches[0]
            writer.writerow(
                {
                    "complaint_id": silver.complaint_id, "category": silver.category,
                    "claimed_amount": str(silver.claimed), "currency": silver.currency.value,
                    "created_at": silver.created_at.isoformat(), "transaction_id": txn.transaction_id,
                    "transaction_amount": str(txn.amount.amount), "transaction_at": txn.occurred_at.isoformat(),
                    "merchant_name": txn.merchant_name or "",
                }
            )  # fmt: skip
    return "written"


def sheet_status(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"status": "not exported"}
    with path.open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    verified = [row for row in rows if row["verified_match"].strip().lower() in {"yes", "no"}]
    if not verified:
        return {"status": "pending", "items": len(rows)}
    yes = sum(row["verified_match"].strip().lower() == "yes" for row in verified)
    return {"status": "verified", "items": len(rows), "verified": len(verified), "precision": yes / len(verified)}


def queries(matches: Sequence[SilverMatch], reader: GoldReader, windows: dict[Country, int]) -> list[Query]:
    """Secondary evaluation queries: claimed amount and the 60-day date range as the descriptor."""
    chosen = unique(matches)[:EVALUATION_SIZE]
    countries = reader.countries(sorted({m.customer_id for m in chosen}))
    own = reader.transactions_of(sorted({m.customer_id for m in chosen}))
    result: list[Query] = []
    for silver in chosen:
        country = countries.get(silver.customer_id)
        if country is None:
            continue
        start = silver.created_at - timedelta(days=windows[country])
        candidates = [t for t in own[silver.customer_id] if start <= t.occurred_at <= silver.created_at]
        window = DateRange(start=(silver.created_at - timedelta(days=WINDOW_DAYS)).date(), end=silver.created_at.date())
        descriptor = TransactionDescriptor(
            amount=silver.claimed, currency_hint=silver.currency, date_interpretations=(window,)
        )
        clues = {"amount": "exact", "merchant": "none", "date": "range", "channel": "none"}
        target = silver.matches[0].transaction_id
        query_id = f"silver:{silver.complaint_id}"
        query = Query(query_id, "silver", "test", "none", country, silver.customer_id, silver.created_at, "", clues,
                      descriptor, candidates, target)  # fmt: skip
        result.append(query)
    return result
