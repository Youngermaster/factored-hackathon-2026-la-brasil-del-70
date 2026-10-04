"""Conversations and their turns, visible only to the owning customer."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from bank_agent.adapters.persistence.postgres.mappers.records import (
    conversation_from_row,
    conversation_to_row,
    turn_from_row,
    turn_to_row,
)
from bank_agent.adapters.persistence.postgres.repositories.access import customer_of
from bank_agent.adapters.persistence.postgres.transaction import Tx
from bank_agent.domain.conversation import (
    DEFAULT_CONVERSATION_CREATION_QUOTA,
    Conversation,
    ConversationCreationQuota,
    Turn,
)
from bank_agent.domain.errors import (
    AccessContextError,
    ConcurrencyConflictError,
    ConversationCreationLimitedError,
    ConversationNotFoundError,
    DuplicateEntityError,
)
from bank_agent.domain.identifiers import ConversationId, TurnId


class PostgresConversationRepository:
    def __init__(self, tx: Tx, creation_quota: ConversationCreationQuota = DEFAULT_CONVERSATION_CREATION_QUOTA) -> None:
        self._tx = tx
        self._quota = creation_quota

    async def get(self, conversation_id: ConversationId) -> Conversation | None:
        row = await self._tx.one_or_none(
            "SELECT document FROM app.conversations WHERE customer_id = :customer AND conversation_id = :id",
            {"customer": customer_of(self._tx.context), "id": conversation_id},
        )
        return conversation_from_row(row) if row is not None else None

    async def add(self, conversation: Conversation) -> None:
        if conversation.customer_id != customer_of(self._tx.context):
            raise AccessContextError("a conversation can only be added for the context customer")
        try:
            await self._tx.guarded(
                "INSERT INTO app.conversations (conversation_id, customer_id, lineage_id, status, created_at, "
                "version, document) VALUES (:conversation_id, :customer_id, :lineage_id, :status, :created_at, "
                ":version, CAST(:document AS jsonb))",
                conversation_to_row(conversation),
            )
        except IntegrityError as error:
            raise DuplicateEntityError("a conversation with this id already exists") from error

    async def add_with_quota(self, conversation: Conversation) -> None:
        customer = customer_of(self._tx.context)
        if conversation.customer_id != customer:
            raise AccessContextError("a conversation can only be added for the context customer")
        locked = await self._tx.scalar(
            "SELECT pg_try_advisory_xact_lock(hashtextextended(:customer, 2600))", {"customer": customer}
        )
        if not locked:
            raise ConcurrencyConflictError("another chat creation is in progress")
        window, limit = self._quota.window, self._quota.limit
        # The newest ``limit`` creations in the window: when there are that many, the oldest of them must leave the
        # window before one more fits (also right after the limit was lowered and the window holds more).
        rows = await self._tx.rows(
            "SELECT created_at FROM app.conversations WHERE customer_id = :customer "
            "AND created_at > :cutoff AND created_at <= :now ORDER BY created_at DESC LIMIT :limit",
            {
                "customer": customer,
                "cutoff": conversation.created_at - window,
                "now": conversation.created_at,
                "limit": limit,
            },
        )
        if len(rows) >= limit:
            blocking = rows[-1]["created_at"]
            if not isinstance(blocking, datetime):
                raise RuntimeError("creation timestamp must be a datetime")
            raise ConversationCreationLimitedError(blocking + window - conversation.created_at)
        await self.add(conversation)

    async def update(self, conversation: Conversation, *, expected_version: int) -> Conversation:
        current = await self.get(conversation.conversation_id)
        if current is None:
            raise ConversationNotFoundError()
        if current.version != expected_version:
            raise ConcurrencyConflictError("the conversation changed since it was read")
        if conversation.customer_id != current.customer_id:
            raise ConcurrencyConflictError("a conversation's owner cannot change")
        stored = conversation.evolve(version=expected_version + 1)
        keys = {"customer": current.customer_id, "id": conversation.conversation_id}
        locked = await self._tx.lock_or_mark_conflicted(
            "SELECT 1 FROM app.conversations WHERE customer_id = :customer AND conversation_id = :id "
            "FOR NO KEY UPDATE NOWAIT",
            keys,
        )
        if not locked:
            return stored
        changed = await self._tx.execute(
            "UPDATE app.conversations SET status = :status, version = :version, document = CAST(:document AS jsonb) "
            "WHERE customer_id = :customer AND conversation_id = :id AND version = :expected",
            {**conversation_to_row(stored), **keys, "expected": expected_version},
        )
        if changed != 1:
            raise ConcurrencyConflictError("the conversation changed since it was read")
        return stored

    async def append_turn(self, turn: Turn) -> None:
        conversation = await self.get(turn.conversation_id)
        if conversation is None:
            raise ConversationNotFoundError()
        try:
            await self._tx.guarded(
                "INSERT INTO app.turns (turn_id, conversation_id, customer_id, sequence, received_at, document) "
                "VALUES (:turn_id, :conversation_id, :customer_id, :sequence, :received_at, "
                "CAST(:document AS jsonb))",
                turn_to_row(turn, conversation.customer_id),
            )
        except IntegrityError as error:
            raise DuplicateEntityError("a turn with this id or sequence number already exists") from error

    async def get_turn(self, turn_id: TurnId) -> Turn | None:
        row = await self._tx.one_or_none(
            "SELECT document FROM app.turns WHERE customer_id = :customer AND turn_id = :id",
            {"customer": customer_of(self._tx.context), "id": turn_id},
        )
        return turn_from_row(row) if row is not None else None

    async def list_turns(self, conversation_id: ConversationId, limit: int = 100) -> Sequence[Turn]:
        rows = await self._tx.rows(
            "SELECT document FROM app.turns WHERE customer_id = :customer AND conversation_id = :id "
            "ORDER BY sequence LIMIT :limit",
            {"customer": customer_of(self._tx.context), "id": conversation_id, "limit": limit},
        )
        return [turn_from_row(row) for row in rows]
