"""Human exchange in the append-only timeline, with a locked handoff as the ordering gate."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from bank_agent.adapters.persistence.postgres.mappers.records import handoff_from_row
from bank_agent.adapters.persistence.postgres.repositories.handoffs import PostgresHandoffRepository
from bank_agent.adapters.persistence.postgres.transaction import Tx
from bank_agent.domain.access import Role
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.errors import (
    AccessContextError,
    ConcurrencyConflictError,
    HandoffNotFoundError,
    IdempotencyConflictError,
    InvalidHandoffTransitionError,
)
from bank_agent.domain.handoff import HandoffRecord, HandoffStatus
from bank_agent.domain.human_service import HumanMessage, HumanMessageReceipt, HumanMessageRole
from bank_agent.domain.identifiers import ConversationId, HandoffId


class PostgresHumanServiceRepository:
    def __init__(self, tx: Tx) -> None:
        self._tx = tx

    async def _authorized(self, handoff_id: HandoffId) -> HandoffRecord:
        context = self._tx.context
        if context.role not in (Role.CUSTOMER, Role.AGENT):
            raise AccessContextError("human messages require a customer or agent context")
        record = await PostgresHandoffRepository(self._tx).get(handoff_id)
        if record is not None and (context.role is Role.CUSTOMER or record.claimed_by == context.staff_id):
            return record
        raise HandoffNotFoundError()

    async def for_conversation(self, conversation_id: ConversationId) -> HandoffRecord | None:
        if self._tx.context.role is not Role.CUSTOMER:
            raise AccessContextError("conversation lookup requires a customer context")
        row = await self._tx.one_or_none(
            "SELECT document, lifecycle FROM app.handoffs WHERE customer_id = :customer "
            "AND document ->> 'conversation_ref' = :conversation "
            "ORDER BY (document ->> 'created_at')::timestamptz DESC, handoff_id DESC LIMIT 1",
            {"customer": self._tx.context.customer_id, "conversation": conversation_id},
        )
        return handoff_from_row(row) if row is not None else None

    async def messages(self, handoff_id: HandoffId, *, after: int = 0, limit: int = 100) -> Sequence[HumanMessage]:
        await self._authorized(handoff_id)
        rows = await self._tx.rows(
            "SELECT message_id, conversation_id, handoff_id, sequence, sent_at, role, text "
            "FROM app.human_messages WHERE handoff_id = :handoff "
            "AND sequence > :after ORDER BY sequence LIMIT :limit",
            {"handoff": handoff_id, "after": after, "limit": limit},
        )
        return [HumanMessage.model_validate(row) for row in rows]

    async def append(self, handoff_id: HandoffId, message_id: str, text: str, *, at: datetime) -> HumanMessageReceipt:
        await self._authorized(handoff_id)
        locked = await self._tx.scalar(
            "SELECT pg_try_advisory_xact_lock(hashtextextended(:id, 26))", {"id": handoff_id}
        )
        if not locked:
            raise ConcurrencyConflictError("the human conversation changed")
        record = await self._authorized(handoff_id)
        role = HumanMessageRole.CUSTOMER if self._tx.context.role is Role.CUSTOMER else HumanMessageRole.AGENT
        existing = await self._tx.one_or_none(
            "SELECT message_id, conversation_id, handoff_id, sequence, sent_at, role, text "
            "FROM app.human_messages WHERE message_id = :id",
            {"id": message_id},
        )
        if existing is not None:
            if existing["handoff_id"] == handoff_id and existing["role"] == role and existing["text"] == text:
                return HumanMessageReceipt(message=HumanMessage.model_validate(existing), replayed=True)
            raise IdempotencyConflictError("message id already used")
        if record.status is HandoffStatus.RESOLVED:
            raise InvalidHandoffTransitionError("the human conversation is closed")
        last = await self._tx.scalar(
            "SELECT COALESCE(max(sequence), 0) FROM app.human_messages WHERE handoff_id = :id",
            {"id": handoff_id},
        )
        if not isinstance(last, int):
            raise RuntimeError("message sequence must be an integer")
        message = HumanMessage(
            message_id=message_id,
            conversation_id=record.handoff.conversation_ref,
            handoff_id=handoff_id,
            sequence=last + 1,
            sent_at=at,
            role=role,
            text=UntrustedText(text),
        )
        try:
            await self._tx.guarded(
                "INSERT INTO app.human_messages (message_id, conversation_id, customer_id, handoff_id, "
                "sequence, sent_at, role, text, staff_id) "
                "VALUES (:id, :conversation, :customer, :handoff, :sequence, :at, :role, :text, :staff)",
                {
                    "id": message_id,
                    "conversation": message.conversation_id,
                    "customer": record.handoff.customer_ref,
                    "handoff": handoff_id,
                    "sequence": message.sequence,
                    "at": at,
                    "role": role.value,
                    "text": text,
                    "staff": self._tx.context.staff_id,
                },
            )
        except IntegrityError as error:
            raise IdempotencyConflictError("message id already used") from error
        return HumanMessageReceipt(message=message, replayed=False)
