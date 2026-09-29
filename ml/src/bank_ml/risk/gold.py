"""Reads the risk estimator's inputs from gold Parquet (DuckDB, read only), in three declared, separate queries.

- Features: ``credit_profiles_serving``, the table the API's ``CreditProfile`` reader serves, so training and serving
  read the same values. Only ``FEATURE_COLUMNS`` are selected; they pass the risk leakage and protected-attribute
  guard at construction.
- Label: open credit products in ``products_serving`` (``LABEL_COLUMNS``), aggregated to the worst known days past
  due and the count of unknown values per customer. Never joined into the feature query.
- Slices: country and segment from ``customers_serving`` and income from ``credit_profiles_serving``
  (``SLICE_COLUMNS``), for the disparity report only. Segment is an age proxy and is never a feature.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb

from bank_agent.adapters.models.risk_features import FEATURE_NAMES
from bank_ml.common.leakage import assert_risk_features_clean
from bank_ml.risk.labels import Outcome

TABLES = ("credit_profiles_serving", "products_serving", "customers_serving")
FEATURE_COLUMNS: tuple[str, ...] = FEATURE_NAMES
KEY_COLUMNS = ("customer_id", "snapshot_date")
LABEL_COLUMNS = ("customer_id", "is_credit_product", "product_status", "days_past_due", "snapshot_date")
SLICE_COLUMNS = ("customer_id", "country", "segment", "estimated_monthly_income")


@dataclass(frozen=True)
class FeatureRow:
    customer_id: str
    snapshot: date
    credit_score: int | None
    tenure_months: int | None
    credit_product_count: int | None
    utilization: Decimal | None


@dataclass(frozen=True)
class SliceRow:
    country: str
    segment: str | None
    income: Decimal | None


class RiskGoldReader:
    def __init__(self, gold_dir: Path) -> None:
        missing = [table for table in TABLES if not (gold_dir / f"{table}.parquet").is_file()]
        if missing:
            raise FileNotFoundError(f"gold tables missing under {gold_dir}: {', '.join(missing)} (make pipeline)")
        assert_risk_features_clean("risk feature reader", FEATURE_COLUMNS)
        self._gold = gold_dir
        self._connection = duckdb.connect()

    def _path(self, table: str) -> str:
        return str(self._gold / f"{table}.parquet")

    def features(self) -> list[FeatureRow]:
        """Customers with at least one open credit product (the label's population), in customer order."""
        rows = self._connection.execute(
            "select customer_id, snapshot_date, credit_score, tenure_months, credit_product_count, utilization "
            "from read_parquet(?) where credit_product_count > 0 order by customer_id",
            [self._path("credit_profiles_serving")],
        ).fetchall()
        return [FeatureRow(*row) for row in rows]

    def outcomes(self) -> dict[str, Outcome]:
        rows = self._connection.execute(
            "select customer_id, max(snapshot_date), max(days_past_due), count(*) filter (where days_past_due is null) "
            "from read_parquet(?) where is_credit_product and product_status <> 'closed' "
            "group by customer_id order by customer_id",
            [self._path("products_serving")],
        ).fetchall()
        return {row[0]: Outcome(row[1], row[2], int(row[3])) for row in rows}

    def slices(self) -> dict[str, SliceRow]:
        rows = self._connection.execute(
            "select c.customer_id, c.country, c.segment, p.estimated_monthly_income "
            "from read_parquet(?) as c left join read_parquet(?) as p on p.customer_id = c.customer_id",
            [self._path("customers_serving"), self._path("credit_profiles_serving")],
        ).fetchall()
        return {row[0]: SliceRow(row[1], row[2], row[3]) for row in rows}

    def close(self) -> None:
        self._connection.close()
