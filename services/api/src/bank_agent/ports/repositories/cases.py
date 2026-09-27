"""Dispute case repository port."""

from collections.abc import Sequence
from typing import Protocol

from bank_agent.domain.dispute import DisputeCase, DisputeStatus
from bank_agent.domain.identifiers import CaseId, IdempotencyKey, TransactionId


class CaseRepository(Protocol):
    """Stores dispute cases.

    Preconditions: bound to an ``AccessContext``. Customers use every method on their own cases. Agents may
    only ``get`` a case that a handoff references. Other combinations raise ``AccessContextError``.
    Postconditions: ``list`` returns the customer's cases, most recently opened first, ties broken by
    ``case_id``. A stored case's ``version`` increases by one on every update.
    Errors: ``add`` with an existing idempotency key and an identical case returns the stored case; with a
    different case it raises ``IdempotencyConflictError``. ``add`` of an existing case id with a different
    key raises ``DuplicateEntityError``. ``update`` raises ``CaseNotFoundError`` for an unknown or foreign
    case and ``ConcurrencyConflictError`` when ``expected_version`` is stale. Adding a case for a customer
    other than the context's raises ``AccessContextError``.
    Isolation: another customer's case behaves exactly like a missing one.
    """

    async def get(self, case_id: CaseId) -> DisputeCase | None:
        """Return the case, or ``None`` when it is unknown or not visible to the context."""
        ...

    async def list(self, statuses: frozenset[DisputeStatus] | None = None, limit: int = 50) -> Sequence[DisputeCase]:
        """Return the customer's cases, optionally only those with the given statuses."""
        ...

    async def find_by_idempotency_key(self, key: IdempotencyKey) -> DisputeCase | None:
        """Return the customer's case created with ``key``, if any."""
        ...

    async def find_open_for_transaction(self, transaction_id: TransactionId) -> DisputeCase | None:
        """Return the customer's case for the transaction that is not resolved or rejected, if any."""
        ...

    async def add(self, case: DisputeCase) -> DisputeCase:
        """Store a new case idempotently and return the stored case."""
        ...

    async def update(self, case: DisputeCase, *, expected_version: int) -> DisputeCase:
        """Replace the stored case when its version equals ``expected_version``; return it with the next version."""
        ...
