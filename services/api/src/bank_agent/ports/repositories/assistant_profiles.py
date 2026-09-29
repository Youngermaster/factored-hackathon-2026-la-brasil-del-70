"""Customer-scoped assistant preferences repository."""

from datetime import datetime
from typing import Protocol

from bank_agent.domain.assistant_profile import AssistantProfile


class AssistantProfileRepository(Protocol):
    """Reads and updates the profile bound to the customer access context.

    Preconditions: bound to a customer ``AccessContext``; name and avatar inputs are validated by the service.
    Postconditions: setters create the profile on first use and update only their own field plus ``updated_at``;
    an unset complementary preference receives its default.
    Errors: ``AccessContextError`` for staff contexts; database constraint errors reject invalid profile values.
    Isolation: no customer identifier is accepted, so a caller can only reach the authenticated customer's
    profile, which is shared across that customer's conversations.
    """

    async def get_mine(self) -> AssistantProfile | None: ...

    async def set_name(self, name: str, *, now: datetime) -> AssistantProfile: ...

    async def set_avatar(self, avatar_key: str, *, now: datetime) -> AssistantProfile: ...
