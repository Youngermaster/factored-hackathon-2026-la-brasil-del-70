"""Assistant profile repository port (ADR 0025)."""

from typing import Protocol

from bank_agent.domain.assistant_profile import AssistantProfile


class AssistantProfileRepository(Protocol):
    """Stores the session customer's assistant profile.

    Preconditions: the unit of work is bound to a customer context; the profile's ``customer_id`` is that
    customer, taken from the session, never from a request body or a model output.
    Postconditions: ``get_current`` returns the saved profile, or the default profile when none was saved.
    ``save`` stores the profile with ``version`` incremented by one and returns it.
    Errors: ``save`` raises ``ConcurrencyConflictError`` when the stored version differs from ``expected_version``, and
    ``AccessContextError`` for a profile of another customer or outside a customer context.
    Isolation: a customer reads and writes only their own profile; row-level security enforces it too.
    """

    async def get_current(self) -> AssistantProfile:
        """The session customer's profile, or the default one."""
        ...

    async def save(self, profile: AssistantProfile, *, expected_version: int) -> AssistantProfile:
        """Store ``profile`` if the stored version is ``expected_version``; return the stored profile."""
        ...
