"""The silver deduplication and as-of exchange-rate macros, rendered from the dbt project and run on tiny frames."""

from datetime import date
from typing import Any

import duckdb
import jinja2
import pandas as pd

from bank_data.settings import DBT_PROJECT_DIR

MACROS = (DBT_PROJECT_DIR / "macros" / "typing.sql").read_text(encoding="utf-8")
META = {
    "transactions": {"primary_key": ["transaction_id"], "order_column": "process_date"},
    "daily_exchange_rates": {
        "primary_key": ["date", "source_currency", "target_currency"],
        "order_column": "_process_date",
    },
}


def _render(call: str) -> str:
    environment = jinja2.Environment(autoescape=False, undefined=jinja2.StrictUndefined)  # noqa: S701 (SQL, not HTML)

    def bronze_meta(table: str, key: str, default: Any) -> Any:
        return META[table].get(key, default)

    def ref(name: str) -> str:
        return name

    environment.globals.update(bronze_meta=bronze_meta, ref=ref)
    return environment.from_string(MACROS + "\n" + call).render()


def test_dedup_keeps_the_latest_partition_then_breaks_ties_deterministically() -> None:
    frame = pd.DataFrame(
        [
            {
                "transaction_id": "T1",
                "status": "pending",
                "process_date": date(2024, 1, 1),
                "_etag": "a",
                "_source_key": "k1",
                "_source_row": 1,
            },
            {
                "transaction_id": "T1",
                "status": "approved",
                "process_date": date(2024, 1, 3),
                "_etag": "b",
                "_source_key": "k3",
                "_source_row": 1,
            },
            {
                "transaction_id": "T2",
                "status": "x",
                "process_date": date(2024, 1, 1),
                "_etag": "a",
                "_source_key": "k1",
                "_source_row": 2,
            },
            {
                "transaction_id": "T2",
                "status": "x",
                "process_date": date(2024, 1, 1),
                "_etag": "a",
                "_source_key": "k1",
                "_source_row": 3,
            },
            {
                "transaction_id": "T3",
                "status": "old",
                "process_date": date(2024, 1, 2),
                "_etag": "a",
                "_source_key": "k2",
                "_source_row": 1,
            },
            {
                "transaction_id": "T3",
                "status": "new",
                "process_date": date(2024, 1, 2),
                "_etag": "z",
                "_source_key": "k2",
                "_source_row": 1,
            },
            {
                "transaction_id": "T4",
                "status": "first",
                "process_date": date(2024, 1, 2),
                "_etag": "a",
                "_source_key": "k2",
                "_source_row": 4,
            },
            {
                "transaction_id": "T4",
                "status": "later",
                "process_date": date(2024, 1, 2),
                "_etag": "a",
                "_source_key": "k2",
                "_source_row": 9,
            },
        ]
    )
    sql = _render("{{ deduplicate('frame', 'transactions') }}")

    connection = duckdb.connect()
    connection.register("frame", frame)
    rows = connection.execute(f"select transaction_id, status, _source_row from ({sql}) order by 1").fetchall()  # noqa: S608

    assert rows == [("T1", "approved", 1), ("T2", "x", 3), ("T3", "new", 1), ("T4", "later", 9)]


def test_dedup_supports_composite_keys() -> None:
    frame = pd.DataFrame(
        [
            {
                "date": date(2024, 1, 1),
                "source_currency": "COP",
                "target_currency": "USD",
                "exchange_rate": 1,
                "_process_date": date(2026, 6, 17),
                "_etag": "a",
                "_source_key": "k",
                "_source_row": 1,
            },
            {
                "date": date(2024, 1, 1),
                "source_currency": "COP",
                "target_currency": "USD",
                "exchange_rate": 2,
                "_process_date": date(2026, 6, 17),
                "_etag": "a",
                "_source_key": "k",
                "_source_row": 2,
            },
            {
                "date": date(2024, 1, 1),
                "source_currency": "ARS",
                "target_currency": "USD",
                "exchange_rate": 3,
                "_process_date": date(2026, 6, 17),
                "_etag": "a",
                "_source_key": "k",
                "_source_row": 3,
            },
        ]
    )
    sql = _render("{{ deduplicate('frame', 'daily_exchange_rates') }}")
    connection = duckdb.connect()
    connection.register("frame", frame)
    rows = connection.execute(f"select source_currency, exchange_rate from ({sql}) order by 1").fetchall()  # noqa: S608
    assert rows == [("ARS", 3), ("COP", 2)]


def test_as_of_join_uses_the_latest_rate_on_or_before_the_business_date() -> None:
    connection = duckdb.connect()
    connection.execute(
        "create table rates as select * from (values "
        "(date '2024-01-01', 'COP', 'USD', 0.00025::decimal(18,6)), "
        "(date '2024-01-03', 'COP', 'USD', 0.00030::decimal(18,6)), "
        "(date '2024-01-01', 'USD', 'COP', 4000::decimal(18,6))) "
        "as t(date, source_currency, target_currency, exchange_rate)"
    )
    connection.execute(
        "create table txns as select * from (values "
        "('T1', date '2024-01-02', 150000.00::decimal(15,2), 'COP'), "
        "('T2', date '2024-01-03', 100000.00::decimal(15,2), 'COP'), "
        "('T3', date '2024-01-02', 12.34::decimal(15,2), 'USD'), "
        "('T4', date '2023-12-31', 1000.00::decimal(15,2), 'COP'), "
        "('T5', date '2024-01-02', 50.00::decimal(15,2), 'ARS')) "
        "as t(transaction_id, process_date, amount, currency)"
    )
    sql = _render("{{ with_recomputed_usd('txns', 'rates') }}")

    rows = connection.execute(f"select transaction_id, recomputed_usd from ({sql}) order by 1").fetchall()  # noqa: S608

    assert [(key, None if value is None else str(value)) for key, value in rows] == [
        ("T1", "37.50"),
        ("T2", "30.00"),
        ("T3", "12.34"),
        ("T4", None),
        ("T5", None),
    ]


def test_snake_macro_matches_the_python_canonical_form() -> None:
    from bank_data.contracts.canonical import snake

    sql = _render("{{ snake(\"'  Call Center / Web '\") }}")
    assert duckdb.sql(f"select {sql}").fetchone() == (snake("  Call Center / Web "),)
