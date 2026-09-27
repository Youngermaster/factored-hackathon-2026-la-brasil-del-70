"""Handoffs: customers add and read their own; agents read every handoff and move its lifecycle."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from bank_agent.adapters.persistence.postgres.mappers.records import handoff_from_row, handoff_to_row
from bank_agent.adapters.persistence.postgres.repositories.access import customer_of, staff_of
from bank_agent.adapters.persistence.postgres.transaction import Tx
from bank_agent.domain.access import Role
from bank_agent.domain.errors import AccessContextError, DuplicateEntityError, HandoffNotFoundError
from bank_agent.domain.handoff import Handoff, HandoffOutcomeCode, HandoffRecord
from bank_agent.domain.identifiers import HandoffId
from bank_agent.ports.repositories.handoffs import HandoffQuery

_INSERT = (
    "INSERT INTO app.handoffs (handoff_id, customer_id, case_ref, application_ref, status, priority, reason_code, "
    "language, sla_due, content_digest, document, lifecycle) VALUES (:handoff_id, :customer_id, :case_ref, "
    ":application_ref, :status, :priority, :reason_code, :language, :sla_due, :content_digest, "
    "CAST(:document AS jsonb), CAST(:lifecycle AS jsonb)) ON CONFLICT (handoff_id, content_digest) DO NOTHING"
)
_ARRAY_FILTERS = (
    ("status", "statuses"),
    ("priority", "priorities"),
    ("reason_code", "reasons"),
    ("language", "languages"),
)


class PostgresHandoffRepository:
    def __init__(self, tx: Tx) -> None:
        self._tx = tx

    async def add(self, handoff: Handoff) -> HandoffRecord:
        if handoff.customer_ref != customer_of(self._tx.context):
            raise AccessContextError("a handoff can only be added for the context customer")
        record = HandoffRecord(handoff=handoff)
        try:
            inserted = await self._tx.guarded(_INSERT, handoff_to_row(record))
        except IntegrityError as error:
            raise DuplicateEntityError("a different handoff with this id already exists") from error
        if inserted == 1:
            return record
        stored = await self.get(handoff.handoff_id)
        if stored is None:
            raise DuplicateEntityError("a different handoff with this id already exists")
        return stored

    async def get(self, handoff_id: HandoffId) -> HandoffRecord | None:
        if self._tx.context.role is Role.AGENT:
            row = await self._tx.one_or_none(
                "SELECT document, lifecycle FROM app.handoffs WHERE handoff_id = :id", {"id": handoff_id}
            )
        else:
            row = await self._tx.one_or_none(
                "SELECT document, lifecycle FROM app.handoffs WHERE customer_id = :customer AND handoff_id = :id",
                {"customer": customer_of(self._tx.context), "id": handoff_id},
            )
        return handoff_from_row(row) if row is not None else None

    async def list(self, query: HandoffQuery) -> Sequence[HandoffRecord]:
        staff_of(self._tx.context, Role.AGENT)
        clauses = ["(CAST(:due AS timestamptz) IS NULL OR sla_due < CAST(:due AS timestamptz))"]
        parameters: dict[str, object] = {"due": query.sla_due_before, "limit": query.limit}
        values = {
            "statuses": [item.value for item in query.statuses],
            "priorities": [item.value for item in query.priorities],
            "reasons": [item.value for item in query.reasons],
            "languages": [item.value for item in query.languages],
        }
        for column, name in _ARRAY_FILTERS:
            if values[name]:
                clauses.append(f"{column} = ANY(:{name})")
                parameters[name] = values[name]
        rows = await self._tx.rows(
            "SELECT document, lifecycle FROM app.handoffs WHERE "  # noqa: S608  # nosec B608 (fixed columns)
            + " AND ".join(clauses)
            + " ORDER BY sla_due, handoff_id LIMIT :limit",
            parameters,
        )
        return [handoff_from_row(row) for row in rows]

    async def _existing(self, handoff_id: HandoffId) -> HandoffRecord:
        row = await self._tx.one_or_none(
            "SELECT document, lifecycle FROM app.handoffs WHERE handoff_id = :id FOR NO KEY UPDATE", {"id": handoff_id}
        )
        if row is None:
            raise HandoffNotFoundError()
        return handoff_from_row(row)

    async def _save_lifecycle(self, record: HandoffRecord) -> HandoffRecord:
        row = handoff_to_row(record)
        await self._tx.execute(
            "UPDATE app.handoffs SET status = :status, lifecycle = CAST(:lifecycle AS jsonb) WHERE handoff_id = :id",
            {"status": row["status"], "lifecycle": row["lifecycle"], "id": record.handoff_id},
        )
        return record

    async def claim(self, handoff_id: HandoffId, *, at: datetime) -> HandoffRecord:
        staff_id = staff_of(self._tx.context, Role.AGENT)
        return await self._save_lifecycle((await self._existing(handoff_id)).claim(staff_id, at))

    async def resolve(
        self, handoff_id: HandoffId, *, outcome: HandoffOutcomeCode, note: str, at: datetime
    ) -> HandoffRecord:
        staff_id = staff_of(self._tx.context, Role.AGENT)
        resolved = (await self._existing(handoff_id)).resolve(staff_id, outcome, note, at)
        return await self._save_lifecycle(resolved)
