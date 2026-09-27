"""Action ledger port: idempotency records for writes that have no idempotency column of their own."""

from typing import Protocol

from bank_agent.domain.actions import ActionKind, ActionLedgerEntry
from bank_agent.domain.identifiers import IdempotencyKey


class ActionLedger(Protocol):
    """Records the first outcome of an idempotent write, per customer, action, and key.

    Preconditions: bound to a customer ``AccessContext``; staff contexts raise ``AccessContextError``.
    Postconditions: ``record`` stores the entry once; later calls with the same key return the stored entry.
    Errors: ``record`` with an existing key and a different ``request_digest`` raises ``IdempotencyConflictError``.
    Isolation: another customer's entries are invisible; the same key used by two customers is two entries.
    """

    async def find(self, action: ActionKind, key: IdempotencyKey) -> ActionLedgerEntry | None:
        """Return the context customer's entry for ``action`` and ``key``, if any."""
        ...

    async def record(self, entry: ActionLedgerEntry) -> ActionLedgerEntry:
        """Store the entry idempotently and return the stored entry."""
        ...
