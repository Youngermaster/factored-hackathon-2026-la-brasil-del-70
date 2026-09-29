"""In-memory adapter for customer-wide assistant preferences."""

from datetime import datetime

from bank_agent.adapters.persistence.memory.repositories import _customer_of
from bank_agent.adapters.persistence.memory.store import TableView
from bank_agent.domain.access import AccessContext
from bank_agent.domain.assistant_profile import AssistantProfile


class InMemoryAssistantProfileRepository:
    def __init__(self, profiles: TableView[str, AssistantProfile], context: AccessContext) -> None:
        self._profiles, self._context = profiles, context

    async def get_mine(self) -> AssistantProfile | None:
        return self._profiles.get(_customer_of(self._context))

    async def set_name(self, name: str, *, now: datetime) -> AssistantProfile:
        customer = _customer_of(self._context)
        current = self._profiles.get(customer)
        profile = AssistantProfile(
            customer_id=customer,
            assistant_name=name,
            avatar_key=current.avatar_key if current else "avatar_1",
            updated_at=now,
        )
        self._profiles.put(customer, profile)
        return profile

    async def set_avatar(self, avatar_key: str, *, now: datetime) -> AssistantProfile:
        customer = _customer_of(self._context)
        current = self._profiles.get(customer)
        profile = AssistantProfile(
            customer_id=customer,
            assistant_name=current.assistant_name if current else "Assistant",
            avatar_key=avatar_key,
            updated_at=now,
        )
        self._profiles.put(customer, profile)
        return profile
