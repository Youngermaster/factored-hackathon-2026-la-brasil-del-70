"""PostgreSQL adapter for customer-wide assistant preferences."""

from datetime import datetime

from bank_agent.adapters.persistence.postgres.repositories.access import customer_of
from bank_agent.adapters.persistence.postgres.transaction import Tx
from bank_agent.domain.assistant_profile import AssistantProfile


class PostgresAssistantProfileRepository:
    def __init__(self, tx: Tx) -> None:
        self._tx = tx

    async def get_mine(self) -> AssistantProfile | None:
        row = await self._tx.one_or_none(
            "SELECT customer_id, assistant_name, avatar_key, updated_at FROM app.assistant_profiles "
            "WHERE customer_id = :customer",
            {"customer": customer_of(self._tx.context)},
        )
        return AssistantProfile(**row) if row is not None else None

    async def set_name(self, name: str, *, now: datetime) -> AssistantProfile:
        customer = customer_of(self._tx.context)
        row = await self._tx.one_or_none(
            "INSERT INTO app.assistant_profiles (customer_id, assistant_name, avatar_key, updated_at) "
            "VALUES (:customer, :name, 'avatar_1', :now) ON CONFLICT (customer_id) DO UPDATE "
            "SET assistant_name = EXCLUDED.assistant_name, updated_at = EXCLUDED.updated_at "
            "RETURNING customer_id, assistant_name, avatar_key, updated_at",
            {"customer": customer, "name": name, "now": now},
        )
        assert row is not None
        return AssistantProfile(**row)

    async def set_avatar(self, avatar_key: str, *, now: datetime) -> AssistantProfile:
        customer = customer_of(self._tx.context)
        row = await self._tx.one_or_none(
            "INSERT INTO app.assistant_profiles (customer_id, assistant_name, avatar_key, updated_at) "
            "VALUES (:customer, 'Assistant', :avatar, :now) ON CONFLICT (customer_id) DO UPDATE "
            "SET avatar_key = EXCLUDED.avatar_key, updated_at = EXCLUDED.updated_at "
            "RETURNING customer_id, assistant_name, avatar_key, updated_at",
            {"customer": customer, "avatar": avatar_key, "now": now},
        )
        assert row is not None
        return AssistantProfile(**row)
