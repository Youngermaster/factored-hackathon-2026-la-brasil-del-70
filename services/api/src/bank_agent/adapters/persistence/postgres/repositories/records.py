"""Execution records and audit events: append-only, replay-safe, readable by evaluators.

An execution record insert uses the ``(turn_id, content_digest)`` arbiter: an identical replay is a no-op, and a
different document for the turn violates the primary key, which becomes ``AppendOnlyViolationError``. Audit
events are appended from contexts that may not read them, so a replay is recognized through
``app.audit_event_digest``, which reveals only the stored digest of one event id.
"""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from bank_agent.adapters.persistence.postgres.mappers.records import (
    audit_from_row,
    audit_to_row,
    record_from_row,
    record_to_row,
)
from bank_agent.adapters.persistence.postgres.repositories.access import customer_of, staff_of
from bank_agent.adapters.persistence.postgres.transaction import Tx
from bank_agent.domain.access import AccessContext, Role
from bank_agent.domain.audit import AuditEvent
from bank_agent.domain.errors import AccessContextError, AppendOnlyViolationError
from bank_agent.domain.execution_record import ExecutionRecord
from bank_agent.domain.identifiers import ConversationId, TurnId
from bank_agent.ports.audit import AuditQuery


class PostgresExecutionRecordRepository:
    def __init__(self, tx: Tx) -> None:
        self._tx = tx

    def _reader(self) -> str | None:
        """The customer whose records are visible, or ``None`` for an evaluator, who sees every record."""
        return None if self._tx.context.role is Role.EVALUATOR else customer_of(self._tx.context)

    async def append(self, record: ExecutionRecord) -> None:
        if record.customer_ref != customer_of(self._tx.context):
            raise AccessContextError("a record can only be appended for the context customer")
        try:
            await self._tx.guarded(
                "INSERT INTO app.execution_records (turn_id, conversation_id, customer_id, recorded_at, "
                "content_digest, document) VALUES (:turn_id, :conversation_id, :customer_id, :recorded_at, "
                ":content_digest, CAST(:document AS jsonb)) ON CONFLICT (turn_id, content_digest) DO NOTHING",
                record_to_row(record),
            )
        except IntegrityError as error:
            raise AppendOnlyViolationError("a turn already has a different execution record") from error

    async def get(self, turn_id: TurnId) -> ExecutionRecord | None:
        row = await self._tx.one_or_none(
            "SELECT document FROM app.execution_records WHERE turn_id = :turn_id "
            "AND (CAST(:customer AS text) IS NULL OR customer_id = CAST(:customer AS text))",
            {"customer": self._reader(), "turn_id": turn_id},
        )
        return record_from_row(row) if row is not None else None

    async def list_for_conversation(self, conversation_id: ConversationId) -> Sequence[ExecutionRecord]:
        rows = await self._tx.rows(
            "SELECT document FROM app.execution_records WHERE conversation_id = :conversation_id "
            "AND (CAST(:customer AS text) IS NULL OR customer_id = CAST(:customer AS text)) "
            "ORDER BY recorded_at, turn_id",
            {"customer": self._reader(), "conversation_id": conversation_id},
        )
        return [record_from_row(row) for row in rows]

    async def count_eligibility_assessments(self, since: datetime) -> int:
        count = await self._tx.scalar(
            "SELECT coalesce(sum(jsonb_array_length(coalesce(document -> 'eligibility_assessments', '[]'::jsonb))), 0) "
            "FROM app.execution_records WHERE customer_id = :customer AND recorded_at >= :since",
            {"customer": customer_of(self._tx.context), "since": since},
        )
        return int(str(count))


class PostgresAuditLog:
    """Implements ``AuditLog`` over one transaction.

    ``customer_id`` is recorded with each event (the context customer, or ``None`` outside a customer
    context); ``list_context`` is the access context that may list events (only an evaluator can).
    """

    def __init__(self, tx: Tx, *, customer_id: str | None, list_context: AccessContext | None) -> None:
        self._tx = tx
        self._customer_id = customer_id
        self._list_context = list_context

    async def append(self, event: AuditEvent) -> None:
        row = audit_to_row(event, self._customer_id)
        inserted = await self._tx.execute(
            "INSERT INTO app.audit_events (event_id, occurred_at, customer_id, actor_role, action, outcome, "
            "content_digest, document) VALUES (:event_id, :occurred_at, :customer_id, :actor_role, :action, "
            ":outcome, :content_digest, CAST(:document AS jsonb)) ON CONFLICT DO NOTHING",
            row,
        )
        if inserted == 1:
            return
        stored = await self._tx.scalar("SELECT app.audit_event_digest(:event_id)", {"event_id": event.event_id})
        if stored != row["content_digest"]:
            raise AppendOnlyViolationError("an audit event with this id already exists")

    async def list(self, query: AuditQuery) -> Sequence[AuditEvent]:
        if self._list_context is None:
            raise AccessContextError("listing audit events needs an evaluator context")
        staff_of(self._list_context, Role.EVALUATOR)
        rows = await self._tx.rows(
            "SELECT document FROM app.audit_events WHERE "
            "(CAST(:since AS timestamptz) IS NULL OR occurred_at >= CAST(:since AS timestamptz)) "
            "AND (CAST(:until AS timestamptz) IS NULL OR occurred_at <= CAST(:until AS timestamptz)) "
            "AND (CAST(:action AS text) IS NULL OR action = CAST(:action AS text)) "
            "ORDER BY occurred_at, event_id LIMIT :limit",
            {"since": query.since, "until": query.until, "action": query.action, "limit": query.limit},
        )
        return [audit_from_row(row) for row in rows]
