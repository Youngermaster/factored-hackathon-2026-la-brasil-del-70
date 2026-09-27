"""Reads the resolver's inputs from the gold serving Parquet files (DuckDB, read only).

Transactions are mapped with the API's own ``transaction_from_row``, so training sees exactly the domain objects
the resolver sees at runtime. ``SOURCE_COLUMNS`` lists every column read; the leakage guard checks them (no
post-outcome column is read; ``affected_product_id`` is never read because it always names another customer's
product, BACKLOG).
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from bank_agent.adapters.persistence.duckdb.gold import GOLD_SCHEMAS
from bank_agent.adapters.persistence.duckdb.readers import transaction_from_row
from bank_agent.domain.locale import Country
from bank_agent.domain.transaction import Transaction
from bank_ml.common.leakage import assert_no_leakage

TRANSACTION_COLUMNS = tuple(name for name, _ in GOLD_SCHEMAS["transactions_serving"])
COMPLAINT_COLUMNS = (
    "complaint_id",
    "customer_id",
    "created_at",
    "category",
    "subcategory",
    "claimed_amount",
    "currency",
)
SOURCE_COLUMNS = (*TRANSACTION_COLUMNS, *COMPLAINT_COLUMNS, "country")
SAMPLE_SALT = "resolver-sample-v1"


@dataclass(frozen=True)
class Complaint:
    complaint_id: str
    customer_id: str
    created_at: object
    category: str
    claimed_amount: object
    currency: str


class GoldReader:
    """Queries over ``<gold>/<table>.parquet``; one connection per reader, in memory."""

    def __init__(self, gold_dir: Path) -> None:
        missing = [
            t for t in ("transactions_serving", "customers_serving") if not (gold_dir / f"{t}.parquet").is_file()
        ]
        if missing:
            raise FileNotFoundError(f"gold tables missing under {gold_dir}: {', '.join(missing)} (make pipeline)")
        assert_no_leakage("resolver gold reader", SOURCE_COLUMNS)
        self._gold = gold_dir
        self._connection = duckdb.connect()

    def _path(self, table: str) -> str:
        return str(self._gold / f"{table}.parquet")

    def countries(self, customer_ids: list[str]) -> dict[str, Country]:
        rows = self._connection.execute(
            "select customer_id, country from read_parquet(?) where customer_id in (select unnest(?))",
            [self._path("customers_serving"), customer_ids],
        ).fetchall()
        return {customer: Country(country) for customer, country in rows if country in Country.__members__}

    def sampled_targets(self, types: tuple[str, ...], share: float) -> list[tuple[str, str, datetime]]:
        """``(transaction_id, customer_id, UTC time)`` of a salted-hash sample of transactions of ``types``."""
        cutoff = int(share * 0xFFFFFFFF)
        rows = self._connection.execute(
            "select transaction_id, customer_id, transaction_at from read_parquet(?) "
            "where transaction_type in (select unnest(?)) "
            "and ('0x' || substr(md5(? || transaction_id), 1, 8))::ubigint < ? "
            "order by transaction_id",
            [self._path("transactions_serving"), list(types), SAMPLE_SALT, cutoff],
        ).fetchall()
        return [(row[0], row[1], row[2].replace(tzinfo=UTC)) for row in rows]

    def latest(self) -> datetime:
        row = self._connection.execute(
            "select max(transaction_at) from read_parquet(?)", [self._path("transactions_serving")]
        ).fetchone()
        if row is None or not isinstance(row[0], datetime):
            raise ValueError("no transactions in gold")
        return row[0].replace(tzinfo=UTC)

    def transactions_of(self, customer_ids: list[str]) -> dict[str, list[Transaction]]:
        columns = ", ".join(TRANSACTION_COLUMNS)
        cursor = self._connection.execute(
            f"select {columns} from read_parquet(?) where customer_id in (select unnest(?)) "  # noqa: S608  # nosec B608
            "order by customer_id, transaction_at, transaction_id",
            [self._path("transactions_serving"), customer_ids],
        )
        found: dict[str, list[Transaction]] = defaultdict(list)
        for values in cursor.fetchall():
            row = dict(zip(TRANSACTION_COLUMNS, values, strict=True))
            found[str(row["customer_id"])].append(transaction_from_row(row))
        return found

    def complaints(self, categories: tuple[str, ...]) -> list[Complaint]:
        path = self._gold / "complaints_serving.parquet"
        if not path.is_file():
            return []
        rows = self._connection.execute(
            "select complaint_id, customer_id, created_at, category, claimed_amount, currency from read_parquet(?) "
            "where category in (select unnest(?)) and claimed_amount is not null order by complaint_id",
            [str(path), list(categories)],
        ).fetchall()
        return [Complaint(*row) for row in rows]

    def close(self) -> None:
        self._connection.close()
