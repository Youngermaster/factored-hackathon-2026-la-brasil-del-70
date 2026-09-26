"""Handoff repository port."""

from collections.abc import Sequence
from datetime import datetime
from typing import Annotated, Protocol

from pydantic import Field

from bank_agent.domain.base import DomainModel, UtcDatetime
from bank_agent.domain.complaint import Priority
from bank_agent.domain.handoff import EscalationReasonCode, Handoff, HandoffOutcomeCode, HandoffRecord, HandoffStatus
from bank_agent.domain.identifiers import HandoffId
from bank_agent.domain.locale import Language


class HandoffQuery(DomainModel):
    """Agent inbox filters. Results are ordered by ``sla_due`` (soonest first), ties broken by ``handoff_id``."""

    statuses: tuple[HandoffStatus, ...] = ()
    priorities: tuple[Priority, ...] = ()
    reasons: tuple[EscalationReasonCode, ...] = ()
    languages: tuple[Language, ...] = ()
    sla_due_before: UtcDatetime | None = None
    limit: Annotated[int, Field(ge=1, le=200)] = 50


class HandoffRepository(Protocol):
    """Stores handoffs and their inbox lifecycle.

    Preconditions: customers ``add`` handoffs about themselves and ``get`` their own; agents ``get``,
    ``list``, ``claim``, and ``resolve`` any handoff, acting as the staff member in the context. Other
    combinations raise ``AccessContextError``.
    Postconditions: the handoff document never changes after ``add``; only the lifecycle does.
    Errors: ``add`` of an existing id with an identical document returns the stored record; with a different
    document it raises ``DuplicateEntityError``. ``claim`` and ``resolve`` raise ``HandoffNotFoundError`` for
    an unknown id and ``InvalidHandoffTransitionError`` for an illegal lifecycle move.
    Isolation: a customer never sees another customer's handoff.
    """

    async def add(self, handoff: Handoff) -> HandoffRecord:
        """Store a new handoff as open and return its record."""
        ...

    async def get(self, handoff_id: HandoffId) -> HandoffRecord | None:
        """Return the record, or ``None`` when it is unknown or not visible."""
        ...

    async def list(self, query: HandoffQuery) -> Sequence[HandoffRecord]:
        """Return the handoffs matching every filter in ``query``."""
        ...

    async def claim(self, handoff_id: HandoffId, *, at: datetime) -> HandoffRecord:
        """Claim an open handoff for the context's agent."""
        ...

    async def resolve(
        self, handoff_id: HandoffId, *, outcome: HandoffOutcomeCode, note: str, at: datetime
    ) -> HandoffRecord:
        """Resolve a handoff the context's agent claimed."""
        ...
