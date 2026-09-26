"""A controllable clock."""

from datetime import UTC, datetime, timedelta


class FixedClock:
    """Implements the ``Clock`` port with an instant that moves only when a test moves it."""

    def __init__(self, at: datetime) -> None:
        self._now = self._checked(at)

    @staticmethod
    def _checked(at: datetime) -> datetime:
        if at.tzinfo is None:
            raise ValueError("FixedClock needs a timezone-aware datetime")
        return at.astimezone(UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> datetime:
        """Move forward by ``delta`` and return the new instant. Moving backwards is refused."""
        if delta < timedelta(0):
            raise ValueError("a clock cannot move backwards")
        self._now += delta
        return self._now

    def set(self, at: datetime) -> None:
        """Jump to ``at``, which must not be earlier than the current instant."""
        checked = self._checked(at)
        if checked < self._now:
            raise ValueError("a clock cannot move backwards")
        self._now = checked
