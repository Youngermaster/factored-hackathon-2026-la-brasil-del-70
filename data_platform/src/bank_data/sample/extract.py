"""The committed, bounded organizer sample (CLAUDE.md rule 5): selection, pseudonymization, and files.

Selection is deterministic and never hand-picked:

1. Customers are ranked by ``sha256(seed || ':' || customer_id)`` (the same expression the dbt sampling uses).
2. Walking that ranking, the first ``min_customers`` are taken; after that a customer is taken only when it
   covers a case the sample still lacks (cards, deposit balances, payments and transfers in every status,
   credit products with and without days past due, income present and missing, a declined card purchase,
   a complaint). The walk stops once everything is covered.
3. Each customer is followed through every table, fact rows limited to the last ``window_days`` of the
   dataset and capped per customer (rare statuses first, then by hash). Branches, agents, campaigns, and
   exchange-rate rows are limited to those the selected rows reference.
4. Direct identifiers are replaced by pseudonyms (``bank_data.sample.pseudonyms``).

Rows are read from bronze (raw strings as delivered, deduplicated like silver) and written back in the bucket
layout, so ``LocalSource`` ingests the sample exactly like the real data. The same dataset version and seed
give byte-identical files.
"""

import csv
import hashlib
import io
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import duckdb

from bank_data.contracts.canonical import canonical_value
from bank_data.contracts.tables import TABLES, TableSpec, table_spec
from bank_data.errors import SampleError
from bank_data.sample import pseudonyms

Row = dict[str, str]
DEFAULT_SEED = "bank-data-sample-v1"
ROW_LIMIT = 5_000
PREVIEW_DIR = "preview"
FACT_CAPS: dict[str, int] = {
    "transactions": 30,
    "call_center_interactions": 5,
    "satisfaction_surveys": 5,
    "complaints": 5,
    "campaign_sends": 3,
    "digital_events": 8,
}
CARD_TYPES = frozenset({"credit_card", "debit_card"})
CREDIT_TYPES = frozenset({"credit_card", "personal_loan", "mortgage"})
DEPOSIT_TYPES = frozenset({"checking_account", "savings_account"})
PAYMENT_STATUSES = ("approved", "declined", "pending", "reversed")
COVERAGE_TARGETS: tuple[str, ...] = (
    "credit_card",
    "debit_card",
    "deposit_with_balance",
    "credit_with_days_past_due",
    "credit_without_days_past_due",
    "income_present",
    "income_missing",
    "declined_card_purchase",
    "complaint",
    *(f"{kind}_{status}" for kind in ("payment", "transfer") for status in PAYMENT_STATUSES),
)


def sample_rank(seed: str, customer_id: str) -> str:
    """The ranking key; equals DuckDB's ``sha256(seed || ':' || customer_id)``."""
    return hashlib.sha256(f"{seed}:{customer_id}".encode()).hexdigest()


@dataclass(frozen=True)
class SampleSettings:
    seed: str = DEFAULT_SEED
    min_customers: int = 70
    min_complaints: int = 5
    """Complaints are rare in the window, and the dispute workflow needs a few (repeat-complainer counts)."""
    max_candidates: int = 3_000
    window_days: int = 365
    preview_rows: int = 10
    row_limit: int = ROW_LIMIT
    required_coverage: tuple[str, ...] = COVERAGE_TARGETS
    allow_whole_tables: bool = False
    """Only for tests on tiny fixtures; the committed sample never copies a whole table (rule 5)."""


@dataclass
class SampleResult:
    customers: list[str]
    tables: dict[str, list[Row]]
    coverage: dict[str, bool]
    source_rows: dict[str, int] = field(default_factory=dict)
    """Row counts of each table in the full delivery (to prove no table is copied whole)."""

    def preview(self, rows: int) -> dict[str, list[Row]]:
        return {name: self.tables[name][:rows] for name in self.tables}


def _canonical(spec: TableSpec, column: str, value: str) -> str:
    domain = spec.column(column).canonical or "snake"
    return canonical_value(domain, value) if value.strip() else ""


class SampleExtractor:
    def __init__(self, bronze_dir: Path, snapshot_date: date, settings: SampleSettings | None = None) -> None:
        self._bronze = bronze_dir
        self._snapshot = snapshot_date
        self._settings = settings or SampleSettings()

    # --- reading ------------------------------------------------------------------------------------------------

    def _connect(self) -> duckdb.DuckDBPyConnection:
        connection = duckdb.connect()
        for spec in TABLES:
            pattern = (self._bronze / spec.name / "**" / "*.parquet").as_posix().replace("'", "''")
            keys = ", ".join(f'trim("{key}")' for key in spec.primary_key)
            order = spec.order_column
            connection.execute(
                f"create view {spec.name} as select * exclude (_rank) from ("  # noqa: S608 (spec names only)
                f'select *, row_number() over (partition by {keys} order by "{order}" desc nulls last, '
                f"_etag desc, _source_key desc, _source_row desc) as _rank "
                f"from read_parquet('{pattern}', union_by_name = true)) where _rank = 1"
            )
        return connection

    @staticmethod
    def _rows(connection: duckdb.DuckDBPyConnection, sql: str, parameters: Sequence[object] = ()) -> list[Row]:
        result = connection.execute(sql, list(parameters))
        names = [column[0] for column in result.description or ()]
        return [
            {name: "" if value is None else str(value) for name, value in zip(names, values, strict=True)}
            for values in result.fetchall()
        ]

    def _candidate_rows(self, connection: duckdb.DuckDBPyConnection, candidates: list[str]) -> dict[str, list[Row]]:
        connection.execute("create temp table candidates (customer_id varchar)")
        connection.executemany("insert into candidates values (?)", [[customer] for customer in candidates])
        start = self._snapshot - timedelta(days=self._settings.window_days - 1)
        found: dict[str, list[Row]] = {}
        for spec in TABLES:
            if spec.customer_column is None:
                continue
            columns = ", ".join(f'"{name}"' for name in spec.column_names)
            window = ""
            parameters: list[object] = []
            if spec.layout == "daily":
                window = " and _process_date between ? and ?"
                parameters = [start, self._snapshot]
            found[spec.name] = self._rows(
                connection,
                f"select {columns}, cast(_process_date as varchar) as _process_date from {spec.name} "  # noqa: S608
                f'where trim("{spec.customer_column}") in (select customer_id from candidates){window}',
                parameters,
            )
        return found

    # --- selection ----------------------------------------------------------------------------------------------

    def _hash(self, *parts: str) -> str:
        return hashlib.sha256(":".join((self._settings.seed, *parts)).encode()).hexdigest()

    def _capped(self, rows: Iterable[Row], table: str, priority: dict[str, int] | None = None) -> list[Row]:
        spec = table_spec(table)
        key = spec.primary_key[0]

        def rank(row: Row) -> tuple[int, str]:
            return (-(priority or {}).get(row[key], 0), self._hash(table, row[key]))

        return sorted(rows, key=rank)[: FACT_CAPS[table]]

    def _select_transactions(self, rows: list[Row], products: Mapping[str, str]) -> list[Row]:
        spec = table_spec("transactions")
        priority: dict[str, int] = {}
        seen: set[tuple[str, str]] = set()
        for row in sorted(rows, key=lambda item: self._hash("transactions", item["transaction_id"])):
            kind = _canonical(spec, "transaction_type", row["transaction_type"])
            status = _canonical(spec, "transaction_status", row["transaction_status"])
            product_type = products.get(row["product_id"], "")
            if kind == "purchase" and status == "declined" and product_type in CARD_TYPES:
                combination = ("declined_card_purchase", "")
            else:
                combination = (kind, status)
            if combination not in seen:
                seen.add(combination)
                priority[row["transaction_id"]] = 2 if status != "approved" or kind in ("payment", "transfer") else 1
        return self._capped(rows, "transactions", priority)

    def _features(self, customer: Row, products: list[Row], transactions: list[Row], complaints: list[Row]) -> set[str]:
        product_spec = table_spec("products")
        transaction_spec = table_spec("transactions")
        features: set[str] = set()
        types = {row["product_id"]: _canonical(product_spec, "product_type", row["product_type"]) for row in products}
        for row in products:
            kind = types[row["product_id"]]
            if kind in CARD_TYPES:
                features.add(kind)
            if kind in DEPOSIT_TYPES and row["current_balance"].strip() and float(row["current_balance"]) > 0:
                features.add("deposit_with_balance")
            if kind in CREDIT_TYPES and row["days_past_due"].strip():
                features.add(
                    "credit_with_days_past_due" if float(row["days_past_due"]) > 0 else "credit_without_days_past_due"
                )
        features.add("income_present" if customer["estimated_monthly_income"].strip() else "income_missing")
        for row in transactions:
            kind = _canonical(transaction_spec, "transaction_type", row["transaction_type"])
            status = _canonical(transaction_spec, "transaction_status", row["transaction_status"])
            if kind in ("payment", "transfer"):
                features.add(f"{kind}_{status}")
            if kind == "purchase" and status == "declined" and types.get(row["product_id"]) in CARD_TYPES:
                features.add("declined_card_purchase")
        if complaints:
            features.add("complaint")
        return features

    def extract(self) -> SampleResult:
        connection = self._connect()
        try:
            return self._extract(connection)
        finally:
            connection.close()

    def _extract(self, connection: duckdb.DuckDBPyConnection) -> SampleResult:
        settings = self._settings
        ranked = self._rows(
            connection,
            "select customer_id from (select distinct trim(customer_id) as customer_id from customers) "
            "where customer_id <> '' order by sha256(? || ':' || customer_id), customer_id limit ?",
            [settings.seed, settings.max_candidates],
        )
        candidates = [row["customer_id"] for row in ranked]
        rows = self._candidate_rows(connection, candidates)
        by_customer: dict[str, dict[str, list[Row]]] = defaultdict(lambda: defaultdict(list))
        for table, table_rows in rows.items():
            column = table_spec(table).customer_column or "customer_id"
            for row in table_rows:
                by_customer[table][row[column].strip()].append(row)

        chosen: list[str] = []
        covered: set[str] = set()
        complaint_total = 0
        selected_transactions: dict[str, list[Row]] = {}
        for customer_id in candidates:
            customer_rows = by_customer["customers"].get(customer_id)
            if not customer_rows:
                continue
            products = by_customer["products"].get(customer_id, [])
            product_types = {
                row["product_id"]: _canonical(table_spec("products"), "product_type", row["product_type"])
                for row in products
            }
            transactions = self._select_transactions(by_customer["transactions"].get(customer_id, []), product_types)
            complaints = _closed_complaints(by_customer["complaints"].get(customer_id, []), set(product_types), set())
            features = self._features(customer_rows[0], products, transactions, complaints)
            wanted_complaints = bool(complaints) and complaint_total < settings.min_complaints
            if len(chosen) < settings.min_customers or features - covered or wanted_complaints:
                chosen.append(customer_id)
                covered |= features
                complaint_total += min(len(complaints), FACT_CAPS["complaints"])
                selected_transactions[customer_id] = transactions
            done = covered >= set(settings.required_coverage) and complaint_total >= settings.min_complaints
            if len(chosen) >= settings.min_customers and done:
                break
        coverage = {target: target in covered for target in COVERAGE_TARGETS}
        coverage["complaint"] = coverage["complaint"] and complaint_total >= settings.min_complaints
        missing = ", ".join(target for target in settings.required_coverage if not coverage[target])
        if missing:
            raise SampleError(f"the first {len(candidates)} ranked customers do not cover: {missing}")

        tables = self._follow(connection, chosen, by_customer, selected_transactions)
        source_rows = {
            spec.name: int((connection.execute(f"select count(*) from {spec.name}").fetchone() or (0,))[0])  # noqa: S608
            for spec in TABLES
        }
        result = SampleResult(customers=chosen, tables=tables, coverage=coverage, source_rows=source_rows)
        self._check_bounds(result)
        return result

    def _follow(
        self,
        connection: duckdb.DuckDBPyConnection,
        chosen: list[str],
        by_customer: Mapping[str, Mapping[str, list[Row]]],
        selected_transactions: Mapping[str, list[Row]],
    ) -> dict[str, list[Row]]:
        tables: dict[str, list[Row]] = {spec.name: [] for spec in TABLES}
        for customer_id in chosen:
            tables["customers"].extend(by_customer["customers"][customer_id][:1])
            products = by_customer["products"].get(customer_id, [])
            tables["products"].extend(products)
            product_ids = {row["product_id"] for row in products}
            tables["transactions"].extend(selected_transactions[customer_id])
            interactions = self._capped(
                by_customer["call_center_interactions"].get(customer_id, []),
                "call_center_interactions",
                {
                    row["interaction_id"]: 1
                    for row in by_customer["call_center_interactions"].get(customer_id, [])
                    if row["has_transcript"].strip().lower() == "true"
                },
            )
            tables["call_center_interactions"].extend(interactions)
            interaction_ids = {row["interaction_id"] for row in interactions}
            tables["call_transcripts"].extend(
                row
                for row in by_customer["call_transcripts"].get(customer_id, [])
                if row["interaction_id"] in interaction_ids
            )
            surveys = [
                row
                for row in by_customer["satisfaction_surveys"].get(customer_id, [])
                if not row["interaction_id"].strip() or row["interaction_id"] in interaction_ids
            ]
            tables["satisfaction_surveys"].extend(self._capped(surveys, "satisfaction_surveys"))
            complaints = _closed_complaints(
                by_customer["complaints"].get(customer_id, []), product_ids, interaction_ids
            )
            tables["complaints"].extend(self._capped(complaints, "complaints"))
            tables["campaign_sends"].extend(
                self._capped(by_customer["campaign_sends"].get(customer_id, []), "campaign_sends")
            )
            events = [
                row
                for row in by_customer["digital_events"].get(customer_id, [])
                if not row["product_id"].strip() or row["product_id"] in product_ids
            ]
            tables["digital_events"].extend(self._capped(events, "digital_events"))

        branch_ids = {row["opening_branch_id"] for row in tables["products"]}
        branch_ids |= {row["registration_branch_id"] for row in tables["customers"]}
        branch_ids |= {row["branch_id"] for row in tables["transactions"]}
        branch_ids |= {row["related_branch_id"] for row in tables["complaints"]}
        agent_ids = {row["agent_id"] for row in tables["call_center_interactions"]}
        agent_ids |= {row["agent_id"] for row in tables["call_transcripts"]}
        agent_ids |= {row["agent_id"] for row in tables["satisfaction_surveys"]}
        agent_ids |= {row["assigned_agent_id"] for row in tables["complaints"]}
        tables["service_agents"] = self._by_keys(connection, "service_agents", "agent_id", agent_ids)
        branch_ids |= {row["assigned_branch_id"] for row in tables["service_agents"]}
        tables["branches"] = self._by_keys(connection, "branches", "branch_id", branch_ids)
        campaign_ids = {row["campaign_id"] for row in tables["campaign_sends"]}
        tables["marketing_campaigns"] = self._by_keys(connection, "marketing_campaigns", "campaign_id", campaign_ids)
        rate_keys = sorted(
            {
                (row["process_date"].strip(), row["currency"].strip())
                for row in tables["transactions"]
                if row["currency"].strip() != "USD" and not row["amount_usd"].strip()
            }
        )
        rates: list[Row] = []
        columns = ", ".join(f'"{name}"' for name in table_spec("daily_exchange_rates").column_names)
        for rate_date, currency in rate_keys:
            rates.extend(
                self._rows(
                    connection,
                    f"select {columns}, cast(_process_date as varchar) as _process_date from daily_exchange_rates "  # noqa: S608
                    "where trim(date) = ? and trim(source_currency) = ? and trim(target_currency) = 'USD'",
                    [rate_date, currency],
                )
            )
        tables["daily_exchange_rates"] = rates
        for spec in TABLES:
            tables[spec.name] = sorted(tables[spec.name], key=_key_of(spec.primary_key))
        return tables

    def _by_keys(self, connection: duckdb.DuckDBPyConnection, table: str, key: str, values: set[str]) -> list[Row]:
        wanted = sorted(value.strip() for value in values if value and value.strip())
        if not wanted:
            return []
        columns = ", ".join(f'"{name}"' for name in table_spec(table).column_names)
        placeholders = ", ".join("?" for _ in wanted)
        return self._rows(
            connection,
            f"select {columns}, cast(_process_date as varchar) as _process_date from {table} "  # noqa: S608
            f'where trim("{key}") in ({placeholders})',
            wanted,
        )

    def _check_bounds(self, result: SampleResult) -> None:
        settings = self._settings
        preview = sum(len(rows) for rows in result.preview(settings.preview_rows).values())
        total = sum(len(rows) for rows in result.tables.values()) + preview
        if total > settings.row_limit:
            raise SampleError(f"the sample would hold {total} rows, above the limit of {settings.row_limit}")
        for name, rows in result.tables.items():
            if not settings.allow_whole_tables and rows and len(rows) >= result.source_rows.get(name, 0):
                raise SampleError(f"the sample would copy the whole {name} table")


def _closed_complaints(rows: Iterable[Row], product_ids: set[str], interaction_ids: set[str]) -> list[Row]:
    """Complaints whose references stay inside the sample. In the delivery, ``affected_product_id`` always names
    another customer's product (phase 03 profiling), so in practice only complaints without one qualify."""
    return [
        row
        for row in rows
        if (not row["affected_product_id"].strip() or row["affected_product_id"] in product_ids)
        and (not row["origin_interaction_id"].strip() or row["origin_interaction_id"] in interaction_ids)
    ]


def _key_of(columns: tuple[str, ...]) -> Callable[[Row], tuple[str, ...]]:
    def key(row: Row) -> tuple[str, ...]:
        return tuple(row[column] for column in columns)

    return key


def pseudonymize(tables: Mapping[str, list[Row]]) -> dict[str, list[Row]]:
    """Replace every direct identifier (``pii`` columns of the table specs) with a deterministic pseudonym."""
    output: dict[str, list[Row]] = {}
    for spec in TABLES:
        rows = [dict(row) for row in tables.get(spec.name, [])]
        pii_columns = [column for column in spec.columns if column.pii is not None]
        avoid = {column.name: {row[column.name] for row in rows} for column in pii_columns}
        key_column = spec.primary_key[0]
        for row in rows:
            key = row[key_column]
            originals = dict(row)
            for column in pii_columns:
                value = originals[column.name]
                if not value.strip():
                    continue
                kind = column.pii
                if kind in ("first_name", "last_name"):
                    row[column.name] = pseudonyms.name(value, spec.name, column.name, key, avoid[column.name])
                elif kind == "document_number":
                    row[column.name] = pseudonyms.shaped(value, spec.name, column.name, key, avoid[column.name])
                elif kind == "product_number":
                    row[column.name] = pseudonyms.shaped(
                        value, spec.name, column.name, key, avoid[column.name], keep_letters=True
                    )
                elif kind == "phone":
                    row[column.name] = pseudonyms.phone(value, spec.name, column.name, key, avoid[column.name])
                elif kind == "address":
                    row[column.name] = pseudonyms.address(spec.name, key, avoid[column.name])
                elif kind == "date_of_birth":
                    original = date.fromisoformat(value.strip())
                    avoided = {date.fromisoformat(item.strip()) for item in avoid[column.name] if item.strip()}
                    row[column.name] = pseudonyms.birth_date(original, spec.name, key, avoided).isoformat()
                elif kind == "ip_address":
                    row[column.name] = pseudonyms.ip_address(spec.name, key, avoid[column.name])
            if "email" in avoid and originals["email"].strip():
                row["email"] = pseudonyms.email(row["first_name"], row["last_name"], spec.name, key, avoid["email"])
        output[spec.name] = rows
    return output


def csv_text(spec: TableSpec, rows: Iterable[Row], *, bom: bool) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(spec.column_names)
    for row in rows:
        writer.writerow([row.get(column, "") for column in spec.column_names])
    return ("\ufeff" if bom else "") + buffer.getvalue()


def layout_files(tables: Mapping[str, list[Row]]) -> dict[str, str]:
    """Relative path to CSV content, in the bucket layout (root snapshots, daily partitions)."""
    files: dict[str, str] = {}
    for spec in TABLES:
        rows = tables.get(spec.name, [])
        if spec.layout == "snapshot":
            files[f"{spec.name}.csv"] = csv_text(spec, rows, bom=True)
            continue
        by_day: dict[str, list[Row]] = defaultdict(list)
        for row in rows:
            by_day[row["_process_date"]].append(row)
        for day, day_rows in sorted(by_day.items()):
            year, month, day_part = day.split("-")
            path = f"{spec.name}/year={year}/month={month}/day={day_part}/{spec.name}_{year}{month}{day_part}.csv"
            files[path] = csv_text(spec, day_rows, bom=True)
    return files


def preview_files(tables: Mapping[str, list[Row]], rows: int) -> dict[str, str]:
    return {
        f"{PREVIEW_DIR}/{spec.name}.csv": csv_text(spec, tables.get(spec.name, [])[:rows], bom=False) for spec in TABLES
    }


def write_sample(output_dir: Path, files: Mapping[str, str]) -> None:
    """Replace every CSV under ``output_dir`` with ``files`` (the README is written separately)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for existing in sorted(output_dir.rglob("*.csv")):
        existing.unlink()
    for directory in sorted(
        (path for path in output_dir.rglob("*") if path.is_dir()), key=lambda p: len(p.parts), reverse=True
    ):
        if not any(directory.iterdir()):
            directory.rmdir()
    for relative, content in sorted(files.items()):
        path = output_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="")
