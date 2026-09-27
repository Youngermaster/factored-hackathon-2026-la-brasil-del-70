"""Alembic environment. Migrations run only through ``bank_agent.adapters.persistence.postgres.migrate``.

The runner opens a connection as the owner role and passes it in ``config.attributes["connection"]``, so this
module never reads the environment or builds a URL itself.
"""

from alembic import context
from sqlalchemy.engine import Connection

VERSION_TABLE_SCHEMA = "app"


def _run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=None,
        version_table_schema=VERSION_TABLE_SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = context.config.attributes.get("connection")
    if not isinstance(connection, Connection):
        raise RuntimeError("run migrations through bank_agent.adapters.persistence.postgres.migrate")
    _run(connection)


if context.is_offline_mode():
    raise RuntimeError("offline migrations are not supported; run them against a database")
run_migrations_online()
