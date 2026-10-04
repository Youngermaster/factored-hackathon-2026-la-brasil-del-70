"""Human-service message repository, scoped to a customer or the agent who claimed the handoff."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from bank_agent.domain.handoff import HandoffRecord
from bank_agent.domain.human_service import HumanMessage, HumanMessageReceipt
from bank_agent.domain.identifiers import ConversationId, HandoffId


class HumanServiceRepository(Protocol):
    """Persists the human exchange without granting staff access to earlier assistant turns.

    Preconditions: bound to a verified customer or agent context. Evaluators are refused.
    Postconditions: messages are append-only, ordered by handoff sequence within the conversation,
    and survive reconnects.
    ``append`` derives the author from the context, serializes against claim/resolve, and replays an identical
    message id without another write. Reusing an id with different content raises ``IdempotencyConflictError``.
    Errors: unauthorized or missing handoffs raise ``HandoffNotFoundError``; sends to resolved handoffs raise
    ``InvalidHandoffTransitionError``; concurrent writes may raise ``ConcurrencyConflictError``.
    Isolation: customers see only their handoffs; agents see messages only for their claimed handoffs, including
    after resolution. Neither operation returns earlier assistant turns or a credit profile.
    """

    async def for_conversation(self, conversation_id: ConversationId) -> HandoffRecord | None:
        """Customer only: the latest handoff of this customer's existing conversation, or None."""
        ...

    async def messages(self, handoff_id: HandoffId, *, after: int = 0, limit: int = 100) -> Sequence[HumanMessage]:
        """A bounded page strictly after a persisted sequence cursor; validate access even for an empty page."""
        ...

    async def append(self, handoff_id: HandoffId, message_id: str, text: str, *, at: datetime) -> HumanMessageReceipt:
        """Append or replay a message as the context's customer or claimed agent; never accept an author id."""
        ...
