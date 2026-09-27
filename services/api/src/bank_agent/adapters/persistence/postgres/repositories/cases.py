"""Dispute cases: idempotent creation, versioned updates, and agent reads limited to referenced cases."""

from collections.abc import Sequence

from sqlalchemy.exc import IntegrityError

from bank_agent.adapters.persistence.postgres.mappers.cases import case_from_row, case_to_row
from bank_agent.adapters.persistence.postgres.repositories.access import customer_of
from bank_agent.adapters.persistence.postgres.transaction import Tx
from bank_agent.domain.access import Role
from bank_agent.domain.dispute import OPEN_STATUSES, DisputeCase, DisputeStatus
from bank_agent.domain.errors import (
    AccessContextError,
    CaseNotFoundError,
    ConcurrencyConflictError,
    DuplicateEntityError,
    IdempotencyConflictError,
)
from bank_agent.domain.identifiers import CaseId, IdempotencyKey, TransactionId

_INSERT = (
    "INSERT INTO app.dispute_cases (case_id, customer_id, transaction_id, product_id, reason, status, opened_at, "
    "idempotency_key, version, document) VALUES (:case_id, :customer_id, :transaction_id, :product_id, :reason, "
    ":status, :opened_at, :idempotency_key, :version, CAST(:document AS jsonb)) "
    "ON CONFLICT (customer_id, idempotency_key) DO NOTHING"
)


def _same_request(left: DisputeCase, right: DisputeCase) -> bool:
    return (left.transaction_id, left.reason, left.disputed_amount) == (
        right.transaction_id,
        right.reason,
        right.disputed_amount,
    )


class PostgresCaseRepository:
    def __init__(self, tx: Tx) -> None:
        self._tx = tx

    async def get(self, case_id: CaseId) -> DisputeCase | None:
        if self._tx.context.role is Role.AGENT:
            row = await self._tx.one_or_none(
                "SELECT c.document FROM app.dispute_cases c WHERE c.case_id = :case_id "
                "AND EXISTS (SELECT 1 FROM app.handoffs h WHERE h.case_ref = c.case_id)",
                {"case_id": case_id},
            )
        else:
            row = await self._tx.one_or_none(
                "SELECT document FROM app.dispute_cases WHERE customer_id = :customer AND case_id = :case_id",
                {"customer": customer_of(self._tx.context), "case_id": case_id},
            )
        return case_from_row(row) if row is not None else None

    async def list(self, statuses: frozenset[DisputeStatus] | None = None, limit: int = 50) -> Sequence[DisputeCase]:
        rows = await self._tx.rows(
            "SELECT document FROM app.dispute_cases WHERE customer_id = :customer "
            "AND (CAST(:statuses AS text[]) IS NULL OR status = ANY(CAST(:statuses AS text[]))) "
            "ORDER BY opened_at DESC, case_id ASC LIMIT :limit",
            {
                "customer": customer_of(self._tx.context),
                "statuses": None if statuses is None else sorted(status.value for status in statuses),
                "limit": limit,
            },
        )
        return [case_from_row(row) for row in rows]

    async def find_by_idempotency_key(self, key: IdempotencyKey) -> DisputeCase | None:
        row = await self._tx.one_or_none(
            "SELECT document FROM app.dispute_cases WHERE customer_id = :customer AND idempotency_key = :key",
            {"customer": customer_of(self._tx.context), "key": key},
        )
        return case_from_row(row) if row is not None else None

    async def find_open_for_transaction(self, transaction_id: TransactionId) -> DisputeCase | None:
        row = await self._tx.one_or_none(
            "SELECT document FROM app.dispute_cases WHERE customer_id = :customer AND transaction_id = :txn "
            "AND status = ANY(:open) ORDER BY opened_at DESC, case_id DESC LIMIT 1",
            {
                "customer": customer_of(self._tx.context),
                "txn": transaction_id,
                "open": sorted(status.value for status in OPEN_STATUSES),
            },
        )
        return case_from_row(row) if row is not None else None

    async def add(self, case: DisputeCase) -> DisputeCase:
        if case.customer_id != customer_of(self._tx.context):
            raise AccessContextError("a case can only be added for the context customer")
        try:
            inserted = await self._tx.guarded(_INSERT, case_to_row(case))
        except IntegrityError as error:
            raise DuplicateEntityError("a case with this id already exists") from error
        if inserted == 1:
            return case
        existing = await self.find_by_idempotency_key(case.idempotency_key)
        if existing is not None and _same_request(existing, case):
            return existing
        raise IdempotencyConflictError()

    async def update(self, case: DisputeCase, *, expected_version: int) -> DisputeCase:
        current = await self.get(case.case_id) if self._tx.context.role is Role.CUSTOMER else None
        if current is None:
            customer_of(self._tx.context)
            raise CaseNotFoundError()
        if current.version != expected_version:
            raise ConcurrencyConflictError("the case changed since it was read")
        if (case.customer_id, case.transaction_id, case.idempotency_key) != (
            current.customer_id,
            current.transaction_id,
            current.idempotency_key,
        ):
            raise ConcurrencyConflictError("a case's owner, transaction, and idempotency key cannot change")
        stored = case.evolve(version=expected_version + 1)
        keys = {"customer": current.customer_id, "case_id": case.case_id}
        locked = await self._tx.lock_or_mark_conflicted(
            "SELECT 1 FROM app.dispute_cases WHERE customer_id = :customer AND case_id = :case_id "
            "FOR NO KEY UPDATE NOWAIT",
            keys,
        )
        if not locked:
            return stored
        row = case_to_row(stored)
        changed = await self._tx.execute(
            "UPDATE app.dispute_cases SET reason = :reason, status = :status, version = :version, "
            "document = CAST(:document AS jsonb) WHERE customer_id = :customer AND case_id = :case_id "
            "AND version = :expected",
            {**keys, **row, "expected": expected_version},
        )
        if changed != 1:
            raise ConcurrencyConflictError("the case changed since it was read")
        return stored
