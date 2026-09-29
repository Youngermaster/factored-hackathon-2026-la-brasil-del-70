"""Customer-scoped assistant preferences repository."""

from datetime import datetime
from typing import Protocol

from bank_agent.domain.assistant_profile import AssistantProfile


class AssistantProfileRepository(Protocol):
    async def get_mine(self) -> AssistantProfile | None: ...

    async def set_name(self, name: str, *, now: datetime) -> AssistantProfile: ...

    async def set_avatar(self, avatar_key: str, *, now: datetime) -> AssistantProfile: ...
