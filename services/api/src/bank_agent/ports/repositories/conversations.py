"""Conversation repository port."""

from collections.abc import Sequence
from typing import Protocol

from bank_agent.domain.conversation import Conversation, Turn
from bank_agent.domain.identifiers import ConversationId, TurnId


class ConversationRepository(Protocol):
    """Stores conversations and their turns.

    Preconditions: bound to a customer ``AccessContext``; staff contexts raise ``AccessContextError``.
    Postconditions: turns are listed by ``sequence``. A stored conversation's ``version`` increases by one
    on every update.
    Errors: ``add`` of an existing id raises ``DuplicateEntityError``; ``update`` raises
    ``ConversationNotFoundError`` for an unknown or foreign conversation and ``ConcurrencyConflictError``
    when ``expected_version`` is stale. ``append_turn`` raises ``ConversationNotFoundError`` when the
    conversation is not visible and ``DuplicateEntityError`` for an existing turn id or sequence number, so
    a retried turn is detected with ``get_turn`` instead of being stored twice.
    Isolation: another customer's conversation and turns behave exactly like missing ones.
    """

    async def get(self, conversation_id: ConversationId) -> Conversation | None:
        """Return the conversation, or ``None`` when it is unknown or belongs to another customer."""
        ...

    async def add(self, conversation: Conversation) -> None:
        """Store a new conversation for the context customer."""
        ...

    async def add_with_quota(self, conversation: Conversation) -> None:
        """Atomically add a newly requested chat, at most five per customer in a rolling 60-minute window.

        Count successful creations strictly after ``created_at - 60 minutes`` across every session and worker.
        Failed or rolled-back creates and messages in existing threads do not count. A full window raises
        ``ConversationCreationLimitedError`` with the time until the oldest counted creation leaves the window.
        Concurrent attempts may raise ``ConcurrencyConflictError``; no excess chat may be committed.
        """
        ...

    async def update(self, conversation: Conversation, *, expected_version: int) -> Conversation:
        """Replace the stored conversation when its version equals ``expected_version``."""
        ...

    async def append_turn(self, turn: Turn) -> None:
        """Store a turn of a visible conversation."""
        ...

    async def get_turn(self, turn_id: TurnId) -> Turn | None:
        """Return the turn, or ``None`` when it is unknown or not visible."""
        ...

    async def list_turns(self, conversation_id: ConversationId, limit: int = 100) -> Sequence[Turn]:
        """Return up to ``limit`` turns of a visible conversation, oldest first; empty when not visible."""
        ...
