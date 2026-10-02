"""The unmerged human-service revision reverses cleanly and restores its restricted grants."""

from sqlalchemy import text

from bank_agent.adapters.persistence.postgres import migrate
from bank_agent_postgres import owner_engine
from bank_agent_test_support import PostgresInstance


async def test_human_service_revision_downgrades_and_upgrades(migrated_postgres: PostgresInstance) -> None:
    engine = owner_engine(migrated_postgres)
    try:
        await migrate.downgrade(engine, app_role=migrated_postgres.app_user, target="0013")
        assert await migrate.current_revision(engine) == "0013"
        async with engine.connect() as connection:
            assert (await connection.execute(text("SELECT to_regclass('app.human_messages')"))).scalar_one() is None
        await migrate.upgrade(engine, app_role=migrated_postgres.app_user)
        async with engine.connect() as connection:
            secured = bool(
                (
                    await connection.execute(
                        text(
                            "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class "
                            "WHERE oid = 'app.human_messages'::regclass"
                        )
                    )
                ).scalar_one()
            )
            assert secured
            privileges = await connection.execute(
                text(
                    "SELECT privilege_type FROM information_schema.role_table_grants "
                    "WHERE table_schema = 'app' AND table_name = 'human_messages' AND grantee = :role"
                ),
                {"role": migrated_postgres.app_user},
            )
            assert {row[0] for row in privileges} == {"SELECT", "INSERT"}
    finally:
        await migrate.upgrade(engine, app_role=migrated_postgres.app_user)
        await engine.dispose()
