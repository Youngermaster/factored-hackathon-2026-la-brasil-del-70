from datetime import date

import pytest

from bank_data.ingest.layout import ObjectLayout, parse_key, relative_key

SNAPSHOT = date(2026, 6, 17)


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("data/customers.csv", ObjectLayout("customers", "snapshot", SNAPSHOT, "csv")),
        ("data/products.parquet", ObjectLayout("products", "snapshot", SNAPSHOT, "parquet")),
        (
            "data/transactions/year=2024/month=01/day=15/transactions_20240115.csv",
            ObjectLayout("transactions", "daily", date(2024, 1, 15), "csv"),
        ),
        (
            "data/digital_events/year=2026/month=06/day=17/part-0.parquet",
            ObjectLayout("digital_events", "daily", date(2026, 6, 17), "parquet"),
        ),
    ],
)
def test_parses_the_two_bucket_layouts(key: str, expected: ObjectLayout) -> None:
    assert parse_key(key, prefix="data/", snapshot_date=SNAPSHOT) == expected


@pytest.mark.parametrize(
    "key",
    [
        "data/unknown_table.csv",
        "data/transactions.csv",
        "data/customers/year=2024/month=01/day=01/customers_20240101.csv",
        "data/transactions/year=2024/month=13/day=01/transactions_20241301.csv",
        "data/transactions/2024/01/01/transactions.csv",
        "data/readme.txt",
        "other/customers.csv",
    ],
)
def test_rejects_keys_outside_the_known_layouts(key: str) -> None:
    assert parse_key(key, prefix="data/", snapshot_date=SNAPSHOT) is None


def test_relative_key_strips_the_prefix_or_rejects_foreign_keys() -> None:
    assert relative_key("data/branches.csv", "data/") == "branches.csv"
    assert relative_key("branches.csv", "") == "branches.csv"
    assert relative_key("elsewhere/branches.csv", "data/") is None
