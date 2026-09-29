"""PostgreSQL readiness check through the application's async engine."""

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine


class PostgresReadinessCheck:
    """Proves the database accepts connections as the application role and accepts writes.

    Implements ``bank_agent.ports.health.ReadinessCheck``. A read-only server (a standby, or
    ``default_transaction_read_only``) is not ready: every request that changes state would fail, and even reads
    refresh the session's last-seen time (degradation level L4).
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    @property
    def name(self) -> str:
        return "database"

    async def check(self) -> bool:
        try:
            async with self._engine.connect() as connection:
                result = await connection.execute(text("SELECT current_setting('transaction_read_only')"))
                return result.scalar_one() == "off"
        except (SQLAlchemyError, OSError):
            return False
