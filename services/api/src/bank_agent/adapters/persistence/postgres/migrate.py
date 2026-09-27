"""Run the Alembic migrations programmatically, as the owner role, over an async engine.

Migrations must run as the role that owns schema ``app`` (``bank_owner``); the application role cannot create
tables. The application role's name is passed to the migrations so they can narrow its privileges.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
VERSION_TABLE_SCHEMA = "app"


def alembic_config(app_role: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.attributes["app_role"] = app_role
    return config


def head_revision() -> str:
    head = ScriptDirectory.from_config(alembic_config("bank_app")).get_current_head()
    if head is None:
        raise RuntimeError("no migration revisions found")
    return head


def _upgrade(connection: Connection, config: Config, target: str) -> None:
    config.attributes["connection"] = connection
    command.upgrade(config, target)


def _downgrade(connection: Connection, config: Config, target: str) -> None:
    config.attributes["connection"] = connection
    command.downgrade(config, target)


def _current(connection: Connection) -> str | None:
    context = MigrationContext.configure(connection, opts={"version_table_schema": VERSION_TABLE_SCHEMA})
    return context.get_current_revision()


async def upgrade(owner_engine: AsyncEngine, *, app_role: str, target: str = "head") -> None:
    """Apply every pending revision up to ``target``. Idempotent: an up-to-date schema is left unchanged."""
    config = alembic_config(app_role)
    async with owner_engine.begin() as connection:
        await connection.run_sync(_upgrade, config, target)


async def downgrade(owner_engine: AsyncEngine, *, app_role: str, target: str) -> None:
    """Revert to ``target`` (``base`` removes everything). For tests and local resets only."""
    config = alembic_config(app_role)
    async with owner_engine.begin() as connection:
        await connection.run_sync(_downgrade, config, target)


async def current_revision(engine: AsyncEngine) -> str | None:
    async with engine.connect() as connection:
        return await connection.run_sync(_current)
