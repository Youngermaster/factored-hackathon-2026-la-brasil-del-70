"""The system clock."""

from datetime import UTC, datetime
from threading import Lock


class SystemClock:
    """Implements the ``Clock`` port with the operating system clock, in UTC.

    If the operating system clock steps backwards (for example after a time synchronization), ``now`` keeps
    returning the latest instant it has already returned, so time never goes backwards within a process.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._latest: datetime | None = None

    def now(self) -> datetime:
        current = datetime.now(UTC)
        with self._lock:
            if self._latest is not None and current < self._latest:
                return self._latest
            self._latest = current
            return current
