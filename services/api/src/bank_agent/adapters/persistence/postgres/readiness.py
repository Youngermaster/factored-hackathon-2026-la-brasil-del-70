"""PostgreSQL readiness check through the application's async engine."""

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine


class PostgresReadinessCheck:
    """Runs ``SELECT 1`` as the application role to prove the database accepts connections.

    Implements ``bank_agent.ports.health.ReadinessCheck``.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    @property
    def name(self) -> str:
        return "database"

    async def check(self) -> bool:
        try:
            async with self._engine.connect() as connection:
                result = await connection.execute(text("SELECT 1"))
                return result.scalar_one() == 1
        except (SQLAlchemyError, OSError):
            return False
