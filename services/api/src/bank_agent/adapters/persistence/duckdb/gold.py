"""The gold serving contract read by the DuckDB adapters.

``bank-data build`` writes these Parquet files under the warehouse ``gold/`` directory. The column lists
below are the serving contract: the data platform integration tests check that the files dbt writes carry
exactly these columns, and the contract suite seeds files with the same schema.

The dataset's credit balance convention was profiled in phase 03 (``docs/data/data-card.md``):
``current_balance`` is never negative on any product and is the amount owed on credit products.
"""

from pathlib import Path

import duckdb

from bank_agent.domain.accounts import CreditBalanceConvention

DATASET_CREDIT_BALANCE_CONVENTION = CreditBalanceConvention.BALANCE_IS_AMOUNT_OWED
"""The convention of the organizer data for ``available_credit`` (credit cards only)."""

GOLD_SCHEMAS: dict[str, tuple[tuple[str, str], ...]] = {
    "customers_serving": (
        ("customer_id", "VARCHAR"),
        ("first_name", "VARCHAR"),
        ("country", "VARCHAR"),
        ("segment", "VARCHAR"),
        ("customer_status", "VARCHAR"),
        ("document_type", "VARCHAR"),
        ("document_number", "VARCHAR"),
        ("mobile_phone", "VARCHAR"),
        ("snapshot_date", "DATE"),
    ),
    "products_serving": (
        ("product_id", "VARCHAR"),
        ("customer_id", "VARCHAR"),
        ("product_type", "VARCHAR"),
        ("product_status", "VARCHAR"),
        ("product_number_last4", "VARCHAR"),
        ("currency", "VARCHAR"),
        ("current_balance", "DECIMAL(15,2)"),
        ("credit_limit", "DECIMAL(15,2)"),
        ("interest_rate", "DECIMAL(5,2)"),
        ("opening_date", "DATE"),
        ("expiration_date", "DATE"),
        ("days_past_due", "BIGINT"),
        ("balance_as_of", "TIMESTAMP"),
        ("has_linked_app", "BOOLEAN"),
        ("is_card", "BOOLEAN"),
        ("is_credit_product", "BOOLEAN"),
        ("snapshot_date", "DATE"),
    ),
    "transactions_serving": (
        ("transaction_id", "VARCHAR"),
        ("customer_id", "VARCHAR"),
        ("product_id", "VARCHAR"),
        ("transaction_at", "TIMESTAMP"),
        ("process_date", "DATE"),
        ("transaction_type", "VARCHAR"),
        ("transaction_category", "VARCHAR"),
        ("amount", "DECIMAL(15,2)"),
        ("currency", "VARCHAR"),
        ("amount_usd", "DECIMAL(15,2)"),
        ("amount_usd_recomputed", "BOOLEAN"),
        ("channel", "VARCHAR"),
        ("transaction_status", "VARCHAR"),
        ("response_code", "VARCHAR"),
        ("merchant_name", "VARCHAR"),
        ("merchant_category", "VARCHAR"),
        ("location_country", "VARCHAR"),
        ("location_city", "VARCHAR"),
        ("is_fraud", "BOOLEAN"),
        ("fraud_score", "DECIMAL(5,2)"),
    ),
    "complaints_serving": (
        ("complaint_id", "VARCHAR"),
        ("customer_id", "VARCHAR"),
        ("created_at", "TIMESTAMP"),
        ("process_date", "DATE"),
        ("case_type", "VARCHAR"),
        ("category", "VARCHAR"),
        ("subcategory", "VARCHAR"),
        ("reception_channel", "VARCHAR"),
        ("affected_product_id", "VARCHAR"),
        ("claimed_amount", "DECIMAL(15,2)"),
        ("currency", "VARCHAR"),
        ("priority", "VARCHAR"),
    ),
    "credit_profiles_serving": (
        ("customer_id", "VARCHAR"),
        ("credit_score", "BIGINT"),
        ("estimated_monthly_income", "DECIMAL(12,2)"),
        ("income_currency", "VARCHAR"),
        ("tenure_months", "BIGINT"),
        ("credit_product_count", "BIGINT"),
        ("max_days_past_due", "BIGINT"),
        ("total_credit_limit", "DECIMAL(38,2)"),
        ("total_credit_limit_currency", "VARCHAR"),
        ("utilization", "DECIMAL(12,4)"),
        ("snapshot_date", "DATE"),
    ),
}


def gold_file(gold_dir: Path, table: str) -> Path:
    return gold_dir / f"{table}.parquet"


def open_gold(gold_dir: Path) -> duckdb.DuckDBPyConnection:
    """An in-memory DuckDB connection with one read-only view per serving file.

    Raises ``FileNotFoundError`` naming the first missing file, so a misconfigured gold directory fails at
    start-up rather than on the first customer request.
    """
    connection = duckdb.connect(":memory:")
    for table in GOLD_SCHEMAS:
        path = gold_file(gold_dir, table)
        if not path.is_file():
            connection.close()
            raise FileNotFoundError(f"gold serving file missing: {path.name}")
        escaped = path.as_posix().replace("'", "''")
        connection.execute(f"create view {table} as select * from read_parquet('{escaped}')")  # noqa: S608 (fixed names)
    return connection
