"""Transactional in-memory human messages with claim ownership and idempotency checks."""

from collections.abc import Sequence
from datetime import datetime

from bank_agent.adapters.persistence.memory.store import TableView
from bank_agent.domain.access import AccessContext, Role
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.errors import (
    AccessContextError,
    HandoffNotFoundError,
    IdempotencyConflictError,
    InvalidHandoffTransitionError,
)
from bank_agent.domain.handoff import HandoffRecord, HandoffStatus
from bank_agent.domain.human_service import HumanMessage, HumanMessageReceipt, HumanMessageRole
from bank_agent.domain.identifiers import ConversationId, HandoffId


class InMemoryHumanServiceRepository:
    def __init__(
        self,
        messages: TableView[str, HumanMessage],
        handoffs: TableView[str, HandoffRecord],
        context: AccessContext,
    ) -> None:
        self._messages, self._handoffs, self._context = messages, handoffs, context

    def _authorized(self, handoff_id: HandoffId) -> HandoffRecord:
        if self._context.role not in (Role.CUSTOMER, Role.AGENT):
            raise AccessContextError("human messages require a customer or agent context")
        record = self._handoffs.get(handoff_id)
        if record is not None:
            if self._context.role is Role.CUSTOMER and record.handoff.customer_ref == self._context.customer_id:
                return record
            if self._context.role is Role.AGENT and record.claimed_by == self._context.staff_id:
                return record
        raise HandoffNotFoundError()

    async def for_conversation(self, conversation_id: ConversationId) -> HandoffRecord | None:
        if self._context.role is not Role.CUSTOMER:
            raise AccessContextError("conversation lookup requires a customer context")
        found = [
            record
            for record in self._handoffs.values()
            if record.handoff.customer_ref == self._context.customer_id
            and record.handoff.conversation_ref == conversation_id
        ]
        return max(found, key=lambda record: (record.handoff.created_at, record.handoff_id), default=None)

    async def messages(self, handoff_id: HandoffId, *, after: int = 0, limit: int = 100) -> Sequence[HumanMessage]:
        self._authorized(handoff_id)
        found = [m for m in self._messages.values() if m.handoff_id == handoff_id and m.sequence > after]
        return sorted(found, key=lambda message: message.sequence)[:limit]

    async def append(self, handoff_id: HandoffId, message_id: str, text: str, *, at: datetime) -> HumanMessageReceipt:
        record = self._authorized(handoff_id)
        role = HumanMessageRole.CUSTOMER if self._context.role is Role.CUSTOMER else HumanMessageRole.AGENT
        existing = self._messages.get(message_id)
        if existing is not None:
            if existing.handoff_id == handoff_id and existing.role is role and existing.text == text:
                return HumanMessageReceipt(message=existing, replayed=True)
            raise IdempotencyConflictError("message id already used")
        if record.status is HandoffStatus.RESOLVED:
            raise InvalidHandoffTransitionError("the human conversation is closed")
        sequence = (
            max(
                (m.sequence for m in self._messages.values() if m.handoff_id == handoff_id),
                default=0,
            )
            + 1
        )
        message = HumanMessage(
            message_id=message_id,
            conversation_id=record.handoff.conversation_ref,
            handoff_id=handoff_id,
            sequence=sequence,
            sent_at=at,
            role=role,
            text=UntrustedText(text),
        )
        # A fresh immutable parent value makes simultaneous sends and lifecycle changes conflict on commit.
        self._handoffs.put(handoff_id, record.evolve())
        self._messages.put(message_id, message)
        return HumanMessageReceipt(message=message, replayed=False)
