"""Turn the selected customers' gold rows into a ``SeedBundle`` of domain objects.

Rows are mapped with the phase 03 gold row mappers, so the seed and the DuckDB readers agree on meaning.
Document numbers and phones never leave this module: only keyed digests reach the identity directory. The
only synthesized records are the open dispute case and the existing credit application that two personas need,
because the organizer data has neither; both are labeled ``seed`` in their identifiers.
"""

import re
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

import duckdb

from bank_agent.adapters.identity.codes import IdentityKeys
from bank_agent.adapters.persistence.duckdb.readers import (
    complaint_from_row,
    credit_profile_from_row,
    product_from_row,
    transaction_from_row,
)
from bank_agent.adapters.persistence.postgres.seed import IdentityEntry, SeedBundle, StaffEntry
from bank_agent.domain.credit import CreditApplicationIntake
from bank_agent.domain.customer import Customer, CustomerSegment, CustomerStatus
from bank_agent.domain.dispute import DisputeCase, DisputeReason
from bank_agent.domain.identifiers import ApplicationId, CaseId, CreditProductCode, CustomerId, IdempotencyKey
from bank_agent.domain.locale import Country
from bank_agent.domain.money import Money
from bank_agent.domain.transaction import Transaction, TransactionStatus, TransactionType
from bank_data.seed.config import PersonaFile
from bank_data.seed.selection import Selection

SEEDED_APPLICATION_PRODUCTS = {Country.MX: "MX-PL-STANDARD", Country.CO: "CO-PL-STANDARD", Country.AR: "AR-PL-STANDARD"}
"""Product codes of seeded application intakes; phase 06 must publish these codes in the synthetic catalog."""
SEEDED_APPLICATION_AMOUNTS = {Country.MX: "60000.00", Country.CO: "20000000.00", Country.AR: "3000000.00"}
DISPUTE_SLA = timedelta(days=15)


def _rows(connection: duckdb.DuckDBPyConnection, table: str, ids: list[str]) -> list[dict[str, Any]]:
    cursor = connection.execute(
        f"SELECT * FROM {table} WHERE customer_id IN (SELECT unnest($ids)) ORDER BY ALL",  # noqa: S608  # nosec B608 (fixed table names)
        {"ids": ids},
    )
    names = [column[0] for column in cursor.description or ()]
    return [dict(zip(names, values, strict=True)) for values in cursor.fetchall()]


def _customer(row: dict[str, Any]) -> Customer:
    return Customer(
        customer_id=CustomerId(row["customer_id"]),
        country=Country(row["country"]),
        segment=CustomerSegment(row["segment"]),
        status=CustomerStatus(row["customer_status"]),
        first_name=row["first_name"],
    )


def _phone_last4(phone: str) -> str:
    return re.sub(r"[^0-9]", "", phone)[-4:]


def _seeded_case(customer_id: str, transactions: list[Transaction]) -> DisputeCase:
    purchases = [
        txn
        for txn in transactions
        if txn.customer_id == customer_id
        and txn.transaction_type is TransactionType.PURCHASE
        and txn.status is TransactionStatus.APPROVED
    ]
    latest = max(purchases, key=lambda txn: (txn.occurred_at, txn.transaction_id))
    opened_at = latest.occurred_at + timedelta(days=1)
    return DisputeCase.open(
        case_id=CaseId(f"case-seed-{customer_id}"),
        transaction=latest,
        reason=DisputeReason.UNRECOGNIZED,
        opened_at=opened_at,
        sla_due_at=opened_at + DISPUTE_SLA,
        idempotency_key=IdempotencyKey(f"seed-open-case-{customer_id}"),
    )


def _seeded_application(customer: Customer, snapshot: date) -> CreditApplicationIntake:
    currency = customer.country.default_currency
    return CreditApplicationIntake.submit(
        application_id=ApplicationId(f"app-seed-{customer.customer_id}"),
        customer_id=customer.customer_id,
        product_code=CreditProductCode(SEEDED_APPLICATION_PRODUCTS[customer.country]),
        requested_amount=Money.of(Decimal(SEEDED_APPLICATION_AMOUNTS[customer.country]), currency),
        requested_term_months=36,
        purpose="general_purpose",
        idempotency_key=IdempotencyKey(f"seed-application-{customer.customer_id}"),
        created_at=datetime.combine(snapshot - timedelta(days=2), time(15, 0), UTC),
    )


def build_bundle(
    connection: duckdb.DuckDBPyConnection,
    personas: PersonaFile,
    selection: Selection,
    keys: IdentityKeys,
    *,
    snapshot: date,
) -> SeedBundle:
    ids = selection.customers
    customer_rows = _rows(connection, "customers_serving", ids)
    customers = [_customer(row) for row in customer_rows]
    products = [product_from_row(row) for row in _rows(connection, "products_serving", ids)]
    owned = {(product.product_id, product.customer_id) for product in products}
    transactions = [
        txn
        for txn in (transaction_from_row(row) for row in _rows(connection, "transactions_serving", ids))
        if (txn.product_id, txn.customer_id) in owned
    ]
    persona_of = {customer_id: persona_id for persona_id, customer_id in selection.personas.items()}
    identities = [
        IdentityEntry(
            customer_id=row["customer_id"],
            persona_id=persona_of.get(row["customer_id"]),
            document_lookup=keys.document_lookup(row["document_number"]),
            phone_last4_lookup=keys.phone_lookup(row["customer_id"], _phone_last4(row["mobile_phone"])),
        )
        for row in customer_rows
    ]
    by_id: dict[str, Customer] = {customer.customer_id: customer for customer in customers}
    flagged = {persona.id: persona for persona in personas.customers}
    cases = [
        _seeded_case(customer_id, transactions)
        for persona_id, customer_id in selection.personas.items()
        if flagged[persona_id].seeded_case
    ]
    applications = [
        _seeded_application(by_id[customer_id], snapshot)
        for persona_id, customer_id in selection.personas.items()
        if flagged[persona_id].seeded_application
    ]
    return SeedBundle(
        customers=customers,
        products=products,
        transactions=transactions,
        complaints=[complaint_from_row(row) for row in _rows(connection, "complaints_serving", ids)],
        credit_profiles=[credit_profile_from_row(row) for row in _rows(connection, "credit_profiles_serving", ids)],
        identities=identities,
        staff=[
            StaffEntry(staff_id=item.staff_id, role=item.role, persona_id=item.id, display_name=item.display_name)
            for item in personas.staff
        ],
        cases=cases,
        credit_applications=applications,
    )
