"""Audit log port."""

from collections.abc import Sequence
from typing import Annotated, Protocol

from pydantic import Field

from bank_agent.domain.audit import AuditEvent
from bank_agent.domain.base import Code, DomainModel, UtcDatetime


class AuditQuery(DomainModel):
    since: UtcDatetime | None = None
    until: UtcDatetime | None = None
    action: Code | None = None
    limit: Annotated[int, Field(ge=1, le=500)] = 100


class AuditLog(Protocol):
    """An append-only log of security-relevant events.

    Two instances exist: ``UnitOfWork.audit``, which commits atomically with the write it describes (tool
    calls), and a standalone log for events outside a customer transaction (login, logout, step-up).
    Preconditions: ``append`` accepts events from any context, including none; ``list`` requires an
    evaluator context.
    Postconditions: ``list`` orders events by ``occurred_at``, ties broken by ``event_id``.
    Errors: appending an identical event again is a no-op; a different event with an existing id raises
    ``AppendOnlyViolationError``. ``list`` outside an evaluator context raises ``AccessContextError``.
    Isolation: events carry only redacted arguments; the log stores what it receives and never widens access.
    """

    async def append(self, event: AuditEvent) -> None:
        """Store the event."""
        ...

    async def list(self, query: AuditQuery) -> Sequence[AuditEvent]:
        """Return the events matching every filter in ``query``."""
        ...
