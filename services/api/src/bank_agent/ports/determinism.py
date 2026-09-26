"""Determinism ports: time and identifiers come from here, so tests can freeze both."""

from datetime import datetime
from typing import Protocol

from bank_agent.domain.identifiers import IdKind


class Clock(Protocol):
    """The current time.

    Preconditions: none.
    Postconditions: ``now`` returns a timezone-aware instant in UTC and never goes backwards within a process.
    Errors: none.
    Isolation: not applicable; time carries no customer data.
    """

    def now(self) -> datetime:
        """Return the current instant."""
        ...


class IdGenerator(Protocol):
    """New identifiers.

    Preconditions: none.
    Postconditions: ``new`` returns an identifier unique within the process, prefixed with the kind (for
    example ``case-...``), that satisfies the identifier pattern and is at most 64 characters long.
    Errors: none.
    Isolation: identifiers encode no customer data; production identifiers are random, so they reveal
    nothing about volume or order.
    """

    def new(self, kind: IdKind) -> str:
        """Return a new identifier of ``kind``."""
        ...
