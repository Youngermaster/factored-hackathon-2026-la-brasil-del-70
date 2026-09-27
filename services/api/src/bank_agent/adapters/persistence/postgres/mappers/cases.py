"""Rows of ``dispute_cases`` and ``credit_applications``: the domain document plus its scalar columns."""

from typing import Any

from bank_agent.adapters.persistence.postgres.mappers.accounts import Row
from bank_agent.adapters.persistence.postgres.mappers.documents import canonical_json, document_of, load_document
from bank_agent.domain.credit import CreditApplicationIntake
from bank_agent.domain.dispute import DisputeCase


def case_from_row(row: Row) -> DisputeCase:
    return load_document(DisputeCase, row["document"])


def case_to_row(case: DisputeCase) -> dict[str, Any]:
    return {
        "case_id": case.case_id,
        "customer_id": case.customer_id,
        "transaction_id": case.transaction_id,
        "product_id": case.product_id,
        "reason": case.reason.value,
        "status": case.status.value,
        "opened_at": case.opened_at,
        "idempotency_key": case.idempotency_key,
        "version": case.version,
        "document": canonical_json(document_of(case)),
    }


def application_from_row(row: Row) -> CreditApplicationIntake:
    return load_document(CreditApplicationIntake, row["document"])


def application_to_row(intake: CreditApplicationIntake) -> dict[str, Any]:
    return {
        "application_id": intake.application_id,
        "customer_id": intake.customer_id,
        "product_code": intake.product_code,
        "status": intake.status.value,
        "requested_amount": intake.requested_amount.amount,
        "currency": intake.requested_amount.currency.value,
        "requested_term_months": intake.requested_term_months,
        "created_at": intake.created_at,
        "idempotency_key": intake.idempotency_key,
        "version": intake.version,
        "document": canonical_json(document_of(intake)),
    }
