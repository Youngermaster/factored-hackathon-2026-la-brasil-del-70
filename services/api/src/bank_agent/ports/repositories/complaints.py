"""Historical complaint repository port."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from bank_agent.domain.complaint import HistoricalComplaint


class HistoricalComplaintReader(Protocol):
    """Reads the bound customer's historical complaints (intake-time fields only).

    Preconditions: bound to a customer ``AccessContext``; ``since`` is timezone-aware.
    Postconditions: complaints created at or after ``since``, newest first, ties broken by ``complaint_id``.
    Errors: ``AccessContextError`` for a staff context.
    Isolation: only the context customer's complaints are visible.
    """

    async def list_since(self, since: datetime) -> Sequence[HistoricalComplaint]:
        """Return the customer's complaints created at or after ``since``."""
        ...

    async def count_since(self, since: datetime) -> int:
        """Return how many complaints the customer created at or after ``since`` (``ESC.repeat_complainer``)."""
        ...


class HistoricalComplaintRepository(HistoricalComplaintReader, Protocol):
    """The full complaint port. It adds no writes: history is read only."""
