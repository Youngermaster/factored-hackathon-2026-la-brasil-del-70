"""DuckDB read adapters over the gold serving Parquet written by ``bank-data build`` (phase 03).

They implement the read-side repository ports (customers, products, transactions, historical complaints,
credit profiles) with the same access rules as the in-memory adapters and pass the same contract suites.
They never write: writes belong to the PostgreSQL adapters (phase 05).
"""
