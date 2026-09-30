"""The retention purge: what it deletes, what it keeps, its boundaries, and who may delete."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from typer.testing import CliRunner

from bank_agent.adapters.persistence.postgres.retention import PostgresRetentionPurge
from bank_agent.cli import app
from bank_agent.testing.clock import FixedClock
from bank_agent_api import ApiBackend, ApiHarness
from bank_agent_postgres import app_engine, owner_engine
from bank_agent_retention import POLICY, chat_at, days, intake_at, row_counts
from bank_agent_scenarios import NOW
from bank_agent_test_support import PostgresInstance

SECOND = days(1 / 86400)
MESSAGE = (
    "INSERT INTO app.messages (message_id, conversation_id, customer_id, sequence, sent_at, role, text) "
    "SELECT 'msg-retention-1', conversation_id, customer_id, 99, :at, 'user', 'fixture text' "
    "FROM app.conversations WHERE conversation_id = :conversation"
)


async def _ids(connection: AsyncConnection, statement: str) -> set[str]:
    return {str(row[0]) for row in await connection.execute(text(statement))}


@pytest.fixture
def harness(postgres_api: ApiBackend) -> ApiHarness:
    return postgres_api.build(clock=FixedClock(NOW - days(100)))


async def test_purges_old_conversation_text_and_ended_sessions_and_keeps_records(
    harness: ApiHarness, migrated_postgres: PostgresInstance
) -> None:
    old = await chat_at(harness, NOW - days(10), "persona-mx")
    recent = await chat_at(harness, NOW - days(1), "persona-co")
    owner = owner_engine(migrated_postgres)
    try:
        before = await row_counts(owner)
        report = await PostgresRetentionPurge(owner).purge(POLICY, NOW)
        after = await row_counts(owner)
        async with owner.connect() as connection:
            left = await _ids(connection, "SELECT conversation_id FROM app.conversations")
    finally:
        await owner.dispose()
    assert left == {recent}
    assert old not in left
    assert report.conversations == 1
    assert report.turns == 1
    assert report.messages == before["messages"] - after["messages"]
    assert report.sessions == 1
    assert report.otp_challenges >= 1
    assert after["execution_records"] == before["execution_records"]
    assert after["audit_events"] == before["audit_events"]
    assert after["sessions"] == before["sessions"] - 1


async def test_the_conversation_boundary_is_exact_to_the_second(
    harness: ApiHarness, migrated_postgres: PostgresInstance
) -> None:
    outside = await chat_at(harness, NOW - days(7) - SECOND, "persona-co")
    inside = await chat_at(harness, NOW - days(7) + SECOND, "persona-mx")
    owner = owner_engine(migrated_postgres)
    try:
        await PostgresRetentionPurge(owner).purge(POLICY, NOW)
        async with owner.connect() as connection:
            left = {
                str(row[0]) for row in await connection.execute(text("SELECT conversation_id FROM app.conversations"))
            }
    finally:
        await owner.dispose()
    assert inside in left
    assert outside not in left


async def test_closed_credit_intakes_expire_and_open_ones_stay(
    harness: ApiHarness, migrated_postgres: PostgresInstance
) -> None:
    factory = harness.container.persistence.uow_factory
    expired = await intake_at(factory, 1, NOW - days(50), withdrawn_at=NOW - days(31))
    recent = await intake_at(factory, 2, NOW - days(50), withdrawn_at=NOW - days(29))
    still_open = await intake_at(factory, 3, NOW - days(90))
    owner = owner_engine(migrated_postgres)
    try:
        report = await PostgresRetentionPurge(owner).purge(POLICY, NOW)
        async with owner.connect() as connection:
            ids = {
                str(row[0])
                for row in await connection.execute(text("SELECT application_id FROM app.credit_applications"))
            }
    finally:
        await owner.dispose()
    assert report.credit_applications == 1
    assert expired not in ids
    assert {recent, still_open} <= ids


async def test_a_dry_run_counts_and_deletes_nothing(harness: ApiHarness, migrated_postgres: PostgresInstance) -> None:
    await chat_at(harness, NOW - days(10), "persona-mx")
    owner = owner_engine(migrated_postgres)
    try:
        before = await row_counts(owner)
        report = await PostgresRetentionPurge(owner).purge(POLICY, NOW, dry_run=True)
        after = await row_counts(owner)
    finally:
        await owner.dispose()
    assert report.dry_run
    assert report.conversations == 1
    assert after == before


async def test_append_only_rows_refuse_deletes_outside_the_retention_context(
    harness: ApiHarness, migrated_postgres: PostgresInstance
) -> None:
    conversation = await chat_at(harness, NOW - days(10), "persona-mx")
    owner, application = owner_engine(migrated_postgres), app_engine(migrated_postgres)
    try:
        async with owner.begin() as connection:
            await connection.execute(text(MESSAGE), {"conversation": conversation, "at": NOW - days(10)})
        async with owner.begin() as connection:
            with pytest.raises(Exception, match="append-only"):
                await connection.execute(text("DELETE FROM app.messages"))
        report = await PostgresRetentionPurge(owner).purge(POLICY, NOW)
        assert report.messages == 1
        async with application.begin() as connection:
            await connection.execute(text("SELECT set_config('app.role', 'retention', true)"))
            with pytest.raises(Exception, match="permission denied"):
                await connection.execute(text("DELETE FROM app.messages"))
    finally:
        await owner.dispose()
        await application.dispose()


def test_the_cli_runs_the_purge_as_the_owner_and_prints_counts_only(
    migrated_postgres: PostgresInstance, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POSTGRES_HOST", migrated_postgres.host)
    monkeypatch.setenv("POSTGRES_PORT", str(migrated_postgres.port))
    monkeypatch.setenv("POSTGRES_DB", migrated_postgres.database)
    monkeypatch.setenv("POSTGRES_ADMIN_USER", migrated_postgres.owner)
    monkeypatch.setenv("POSTGRES_ADMIN_PASSWORD", migrated_postgres.owner_password)

    result = CliRunner().invoke(app, ["retention", "purge", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert '"event": "retention_purge"' in result.output
    assert '"dry_run": true' in result.output
    assert migrated_postgres.owner_password not in result.output


def test_the_cli_needs_the_owner_password() -> None:
    result = CliRunner().invoke(app, ["retention", "purge"])
    assert result.exit_code == 2
    assert "POSTGRES_ADMIN_PASSWORD" in result.output


def test_the_repeating_purge_survives_a_failed_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_ADMIN_PASSWORD", "unused-in-this-test-because-the-port-is-closed")
    monkeypatch.setenv("POSTGRES_PORT", "1")

    class StopError(Exception):
        pass

    def stop(_: float) -> None:
        raise StopError

    monkeypatch.setattr("bank_agent.cli.time.sleep", stop)
    result = CliRunner().invoke(app, ["retention", "purge", "--every-hours", "24"])

    assert isinstance(result.exception, StopError)
    assert "retention_purge_failed" in result.output
