"""Credit application repository port."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from bank_agent.domain.credit import ApplicationStatus, CreditApplicationIntake
from bank_agent.domain.identifiers import ApplicationId


class CreditApplicationRepository(Protocol):
    """Stores credit application intakes recorded for human review.

    Preconditions: bound to an ``AccessContext``. Customers use every method except ``list_for_review`` on their
    own applications. An agent may only ``get`` and ``list_for_review`` reviewable applications (status
    ``submitted`` or ``under_human_review``, each a review item of its own) and any application that a handoff's
    ``credit_review.application_ref`` references (phase 16 adds the agent review moves). Other combinations raise
    ``AccessContextError``.
    Postconditions: ``list_mine`` returns the customer's applications, most recent first, ties broken by
    ``application_id``. A stored application's ``version`` increases by one on every transition.
    Errors: ``create`` with an existing idempotency key and the same request returns the stored intake; with a
    different request it raises ``IdempotencyConflictError``; an existing id with another key raises
    ``DuplicateEntityError``; an intake for another customer raises ``AccessContextError``. ``transition``
    raises ``CreditApplicationNotFoundError`` for an unknown or foreign id, ``ConcurrencyConflictError`` for a
    stale ``expected_version``, ``InvalidApplicationTransitionError`` for an illegal move, and
    ``AccessContextError`` when a customer attempts a move other than ``withdrawn``.
    Isolation: another customer's application behaves exactly like a missing one.
    """

    async def create(self, intake: CreditApplicationIntake) -> CreditApplicationIntake:
        """Store a new intake idempotently and return the stored intake."""
        ...

    async def get(self, application_id: ApplicationId) -> CreditApplicationIntake | None:
        """Return the application, or ``None`` when it is unknown or not visible to the context."""
        ...

    async def list_mine(
        self, statuses: frozenset[ApplicationStatus] | None = None, limit: int = 50
    ) -> Sequence[CreditApplicationIntake]:
        """Return the customer's applications, optionally only those with the given statuses."""
        ...

    async def list_for_review(
        self, statuses: frozenset[ApplicationStatus] | None = None, limit: int = 50
    ) -> Sequence[CreditApplicationIntake]:
        """Agents: the applications visible for review, most recent first, ties broken by ``application_id``."""
        ...

    async def transition(
        self,
        application_id: ApplicationId,
        status: ApplicationStatus,
        *,
        expected_version: int,
        at: datetime,
        reason_code: str,
    ) -> CreditApplicationIntake:
        """Move the application to ``status`` and return it with the next version."""
        ...
