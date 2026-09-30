"""Credit application intakes: idempotent creation, customer withdrawal, agent reads and review moves."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from bank_agent.adapters.persistence.postgres.mappers.cases import application_from_row, application_to_row
from bank_agent.adapters.persistence.postgres.repositories.access import customer_of, staff_of
from bank_agent.adapters.persistence.postgres.transaction import Tx
from bank_agent.domain.access import Role
from bank_agent.domain.credit import (
    CUSTOMER_APPLICATION_TRANSITIONS,
    REVIEWABLE_APPLICATION_STATUSES,
    REVIEWER_APPLICATION_TRANSITIONS,
    ApplicationStatus,
    CreditApplicationIntake,
)
from bank_agent.domain.errors import (
    AccessContextError,
    ConcurrencyConflictError,
    CreditApplicationNotFoundError,
    DuplicateEntityError,
    IdempotencyConflictError,
)
from bank_agent.domain.identifiers import ApplicationId

_INSERT = (
    "INSERT INTO app.credit_applications (application_id, customer_id, product_code, status, requested_amount, "
    "currency, requested_term_months, created_at, idempotency_key, version, document) VALUES (:application_id, "
    ":customer_id, :product_code, :status, :requested_amount, :currency, :requested_term_months, :created_at, "
    ":idempotency_key, :version, CAST(:document AS jsonb)) ON CONFLICT (customer_id, idempotency_key) DO NOTHING"
)

# Agents see every reviewable intake and any intake a handoff references; row-level security agrees (0010).
_AGENT_GET = (
    "SELECT a.document FROM app.credit_applications a WHERE a.application_id = :application_id "
    "AND (a.status = ANY(CAST(:reviewable AS text[])) "
    "OR EXISTS (SELECT 1 FROM app.handoffs h WHERE h.application_ref = a.application_id))"
)
_AGENT_LIST = (
    "SELECT a.document FROM app.credit_applications a WHERE (a.status = ANY(CAST(:reviewable AS text[])) "
    "OR EXISTS (SELECT 1 FROM app.handoffs h WHERE h.application_ref = a.application_id)) "
    "AND (CAST(:statuses AS text[]) IS NULL OR a.status = ANY(CAST(:statuses AS text[]))) "
    "ORDER BY a.created_at DESC, a.application_id ASC LIMIT :limit"
)
_REVIEWABLE = sorted(status.value for status in REVIEWABLE_APPLICATION_STATUSES)


class PostgresCreditApplicationRepository:
    def __init__(self, tx: Tx) -> None:
        self._tx = tx

    async def _own_by_key(self, key: str) -> CreditApplicationIntake | None:
        row = await self._tx.one_or_none(
            "SELECT document FROM app.credit_applications WHERE customer_id = :customer AND idempotency_key = :key",
            {"customer": customer_of(self._tx.context), "key": key},
        )
        return application_from_row(row) if row is not None else None

    async def create(self, intake: CreditApplicationIntake) -> CreditApplicationIntake:
        if intake.customer_id != customer_of(self._tx.context):
            raise AccessContextError("an application can only be created for the context customer")
        try:
            inserted = await self._tx.guarded(_INSERT, application_to_row(intake))
        except IntegrityError as error:
            raise DuplicateEntityError("an application with this id already exists") from error
        if inserted == 1:
            return intake
        existing = await self._own_by_key(intake.idempotency_key)
        if existing is not None and existing.same_request(intake):
            return existing
        raise IdempotencyConflictError()

    async def get(self, application_id: ApplicationId) -> CreditApplicationIntake | None:
        if self._tx.context.role is Role.AGENT:
            row = await self._tx.one_or_none(
                _AGENT_GET,
                {"application_id": application_id, "reviewable": _REVIEWABLE},
            )
        else:
            row = await self._tx.one_or_none(
                "SELECT document FROM app.credit_applications WHERE customer_id = :customer "
                "AND application_id = :application_id",
                {"customer": customer_of(self._tx.context), "application_id": application_id},
            )
        return application_from_row(row) if row is not None else None

    async def list_mine(
        self, statuses: frozenset[ApplicationStatus] | None = None, limit: int = 50
    ) -> Sequence[CreditApplicationIntake]:
        rows = await self._tx.rows(
            "SELECT document FROM app.credit_applications WHERE customer_id = :customer "
            "AND (CAST(:statuses AS text[]) IS NULL OR status = ANY(CAST(:statuses AS text[]))) "
            "ORDER BY created_at DESC, application_id ASC LIMIT :limit",
            {
                "customer": customer_of(self._tx.context),
                "statuses": None if statuses is None else sorted(status.value for status in statuses),
                "limit": limit,
            },
        )
        return [application_from_row(row) for row in rows]

    async def list_for_review(
        self, statuses: frozenset[ApplicationStatus] | None = None, limit: int = 50
    ) -> Sequence[CreditApplicationIntake]:
        staff_of(self._tx.context, Role.AGENT)
        rows = await self._tx.rows(
            _AGENT_LIST,
            {
                "statuses": None if statuses is None else sorted(status.value for status in statuses),
                "limit": limit,
                "reviewable": _REVIEWABLE,
            },
        )
        return [application_from_row(row) for row in rows]

    async def transition(
        self,
        application_id: ApplicationId,
        status: ApplicationStatus,
        *,
        expected_version: int,
        at: datetime,
        reason_code: str,
    ) -> CreditApplicationIntake:
        if self._tx.context.role is Role.AGENT:
            if status not in REVIEWER_APPLICATION_TRANSITIONS:
                raise AccessContextError("an agent can only take an application into review or close it")
        else:
            customer_of(self._tx.context)
            if status not in CUSTOMER_APPLICATION_TRANSITIONS:
                raise AccessContextError("a customer can only withdraw an application")
        current = await self.get(application_id)
        if current is None:
            raise CreditApplicationNotFoundError()
        if current.version != expected_version:
            raise ConcurrencyConflictError("the application changed since it was read")
        moved = current.transition_to(status, at=at, reason_code=reason_code).evolve(version=expected_version + 1)
        keys = {"customer": current.customer_id, "application_id": application_id}
        locked = await self._tx.lock_or_mark_conflicted(
            "SELECT 1 FROM app.credit_applications WHERE customer_id = :customer "
            "AND application_id = :application_id FOR NO KEY UPDATE NOWAIT",
            keys,
        )
        if not locked:
            return moved
        row = application_to_row(moved)
        changed = await self._tx.execute(
            "UPDATE app.credit_applications SET status = :status, version = :version, "
            "document = CAST(:document AS jsonb) WHERE customer_id = :customer "
            "AND application_id = :application_id AND version = :expected",
            {**row, **keys, "expected": expected_version},
        )
        if changed != 1:
            raise ConcurrencyConflictError("the application changed since it was read")
        return moved
