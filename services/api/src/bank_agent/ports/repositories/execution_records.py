"""Execution record repository port."""

from collections.abc import Sequence
from typing import Protocol

from bank_agent.domain.execution_record import ExecutionRecord
from bank_agent.domain.identifiers import ConversationId, TurnId


class ExecutionRecordRepository(Protocol):
    """Stores one execution record per turn. Append-only: no method updates or deletes a record.

    Preconditions: customers append and read records whose ``customer_ref`` is their own; evaluators read
    every record; agents raise ``AccessContextError``, as do evaluators appending.
    Postconditions: ``list_for_conversation`` orders records by ``recorded_at``, ties broken by ``turn_id``.
    Errors: appending an identical record for an existing turn is a no-op; a different record for the same
    turn raises ``AppendOnlyViolationError``. Appending a record for another customer raises
    ``AccessContextError``.
    Isolation: another customer's records are invisible to a customer context.
    """

    async def append(self, record: ExecutionRecord) -> None:
        """Store the record for its turn."""
        ...

    async def get(self, turn_id: TurnId) -> ExecutionRecord | None:
        """Return the record of the turn, or ``None`` when it is unknown or not visible."""
        ...

    async def list_for_conversation(self, conversation_id: ConversationId) -> Sequence[ExecutionRecord]:
        """Return the visible records of a conversation."""
        ...
