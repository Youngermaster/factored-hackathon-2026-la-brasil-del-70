"""Determinism ports: time and identifiers come from here, so tests can freeze both."""

from datetime import datetime
from typing import Protocol

from bank_agent.domain.identifiers import IdKind


class Clock(Protocol):
    """The current time.

    Postconditions: ``now`` returns a timezone-aware instant in UTC and never goes backwards within a process.
    """

    def now(self) -> datetime:
        """Return the current instant."""
        ...


class IdGenerator(Protocol):
    """New identifiers.

    Postconditions: ``new`` returns an identifier unique within the process, prefixed with the kind (for
    example ``case-...``), that satisfies the identifier pattern and is at most 64 characters long.
    """

    def new(self, kind: IdKind) -> str:
        """Return a new identifier of ``kind``."""
        ...
