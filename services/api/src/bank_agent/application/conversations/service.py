"""Conversation use cases: open a conversation, send a turn, read the history, read the execution records.

Every call runs under the caller's session, so repositories scope it: another customer's conversation behaves
exactly like a missing one (``ConversationNotFoundError``, a 404). The engine owns the turn; this service adds the
explicit open, the turn id check, and the reads.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from bank_agent.application.engine.engine import TurnRequest, WorkflowEngine
from bank_agent.domain.access import Role
from bank_agent.domain.audit import AuditEvent, AuditOutcome
from bank_agent.domain.conversation import Conversation, Turn, TurnResult
from bank_agent.domain.errors import AccessContextError, ConversationNotFoundError, TurnConflictError
from bank_agent.domain.execution_record import ExecutionRecord
from bank_agent.domain.identifiers import AuditEventId, ConversationId, IdKind, SourceRef, SourceTable, TurnId
from bank_agent.domain.session import Session
from bank_agent.ports.determinism import Clock, IdGenerator
from bank_agent.ports.unit_of_work import UnitOfWorkFactory

MAX_HISTORY_TURNS = 200


@dataclass(frozen=True)
class ConversationHistory:
    conversation: Conversation
    turns: Sequence[Turn]


def _customer_only(session: Session) -> None:
    if session.role is not Role.CUSTOMER:
        raise AccessContextError("conversations belong to customer sessions")


class ConversationService:
    def __init__(self, engine: WorkflowEngine, uow_factory: UnitOfWorkFactory, clock: Clock, ids: IdGenerator) -> None:
        self._engine, self._uow_factory, self._clock, self._ids = engine, uow_factory, clock, ids

    async def open(self, session: Session) -> Conversation:
        """Create an empty conversation for the session's customer and audit it."""
        _customer_only(session)
        now = self._clock.now()
        async with self._uow_factory(session.access_context()) as uow:
            customer = await uow.customers.get_current()
            conversation = self._engine.new_conversation(session, customer, now)
            await uow.conversations.add(conversation)
            await uow.audit.append(
                AuditEvent(
                    event_id=AuditEventId(self._ids.new(IdKind.AUDIT_EVENT)),
                    occurred_at=now,
                    actor_role=session.role,
                    actor_ref=session.customer_id,
                    action="conversation_created",
                    target=SourceRef.of(SourceTable.CONVERSATIONS, conversation.conversation_id),
                    outcome=AuditOutcome.SUCCESS,
                    arguments={"session_id": session.session_id},
                )
            )
            await uow.commit()
        return conversation

    async def send(self, session: Session, conversation_id: ConversationId, turn_id: TurnId, text: str) -> TurnResult:
        """Process one customer message. A repeated turn id replays; one from another conversation conflicts."""
        _customer_only(session)
        result = await self._engine.process_turn(
            TurnRequest(turn_id=turn_id, text=text, session=session, conversation_id=conversation_id)
        )
        if result.conversation_id != conversation_id:
            raise TurnConflictError()
        return result

    async def history(self, session: Session, conversation_id: ConversationId) -> ConversationHistory:
        _customer_only(session)
        async with self._uow_factory(session.access_context()) as uow:
            conversation = await uow.conversations.get(conversation_id)
            if conversation is None:
                raise ConversationNotFoundError()
            turns = await uow.conversations.list_turns(conversation_id, limit=MAX_HISTORY_TURNS)
        return ConversationHistory(conversation=conversation, turns=turns)

    async def trace(self, session: Session, conversation_id: ConversationId) -> Sequence[ExecutionRecord]:
        """Execution records: a customer reads their own conversation's, an evaluator reads any conversation's."""
        if session.role not in (Role.CUSTOMER, Role.EVALUATOR):
            raise AccessContextError("execution records are for customers and evaluators")
        async with self._uow_factory(session.access_context()) as uow:
            if session.role is Role.CUSTOMER and await uow.conversations.get(conversation_id) is None:
                raise ConversationNotFoundError()
            records = await uow.execution_records.list_for_conversation(conversation_id)
        if session.role is Role.EVALUATOR and not records:
            raise ConversationNotFoundError()
        return records
