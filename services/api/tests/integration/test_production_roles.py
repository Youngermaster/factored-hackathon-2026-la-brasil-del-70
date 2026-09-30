"""The whole schema under the production roles: a non-superuser owner, so forced row-level security binds it too.

Development and the other suites use the image's bootstrap superuser as the owner, which bypasses row-level
security. This suite starts its own PostgreSQL with ``deploy/postgres/init-production`` (the script
``deploy/compose.prod.yml`` uses), migrates and seeds as the non-superuser owner, and proves the seed policies, the
forced RLS on the owner, the audit replay check, the API, the rate limits, and the retention purge.
"""

import asyncio
import secrets
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from sqlalchemy import text
from testcontainers.community.postgres import PostgresContainer

from bank_agent.adapters.persistence.postgres import migrate
from bank_agent.adapters.persistence.postgres.rate_limits import PostgresRateLimitStore, rate_limit_key
from bank_agent.adapters.persistence.postgres.retention import PostgresRetentionPurge
from bank_agent.adapters.persistence.postgres.seed import PostgresSeeder, SeedBundle
from bank_agent.testing.clock import FixedClock
from bank_agent_api import ApiClient, api_environment, build_api, postgres_identities
from bank_agent_postgres import REPOSITORY_ROOT, app_engine, compose_postgres_image, owner_engine
from bank_agent_retention import POLICY
from bank_agent_scenarios import MX, NOW, scenario_data
from bank_agent_test_support import PostgresInstance

INIT_PRODUCTION = REPOSITORY_ROOT / "deploy" / "postgres" / "init-production"


async def _prepare(instance: PostgresInstance) -> None:
    owner = owner_engine(instance)
    try:
        await migrate.upgrade(owner, app_role=instance.app_user)
        data = scenario_data()
        identities, staff = postgres_identities()
        bundle = SeedBundle(
            customers=data.customers,
            products=data.products,
            transactions=data.transactions,
            cases=data.cases,
            credit_profiles=data.credit_profiles,
            identities=identities,
            staff=staff,
        )
        await PostgresSeeder(owner).load(bundle)
        await PostgresSeeder(owner).load(bundle)  # the seed is repeatable under the production roles
    finally:
        await owner.dispose()


@pytest.fixture(scope="module")
def production_postgres() -> Iterator[PostgresInstance]:
    passwords = {name: secrets.token_urlsafe(24) for name in ("superuser", "owner", "app")}
    container = (
        PostgresContainer(
            compose_postgres_image(),
            username="postgres",
            password=passwords["superuser"],
            dbname="bank_agent",
            driver=None,
        )
        .with_env("POSTGRES_OWNER_USER", "bank_owner")
        .with_env("POSTGRES_OWNER_PASSWORD", passwords["owner"])
        .with_env("POSTGRES_APP_USER", "bank_app")
        .with_env("POSTGRES_APP_PASSWORD", passwords["app"])
        .with_volume_mapping(str(INIT_PRODUCTION), "/docker-entrypoint-initdb.d", "ro")
    )
    with container:
        instance = PostgresInstance(
            host=container.get_container_host_ip(),
            port=int(container.get_exposed_port(5432)),
            database="bank_agent",
            owner="bank_owner",
            owner_password=passwords["owner"],
            app_user="bank_app",
            app_password=passwords["app"],
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(asyncio.run, _prepare(instance)).result()
        yield instance


async def test_no_service_role_has_superuser_powers(production_postgres: PostgresInstance) -> None:
    owner = owner_engine(production_postgres)
    try:
        async with owner.connect() as connection:
            rows = await connection.execute(
                text(
                    "SELECT rolname, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb FROM pg_roles "
                    "WHERE rolname IN ('bank_owner', 'bank_app', 'bank_evaluator') ORDER BY rolname"
                )
            )
            roles = {row.rolname: (row.rolsuper, row.rolbypassrls, row.rolcreaterole, row.rolcreatedb) for row in rows}
            revision = await migrate.current_revision(owner)
            foreign = await connection.execute(
                text(
                    "SELECT count(*) FROM pg_tables WHERE schemaname IN ('app', 'eval') AND tableowner <> 'bank_owner'"
                )
            )
            foreign_tables = int(foreign.scalar_one())
    finally:
        await owner.dispose()
    assert roles == dict.fromkeys(("bank_app", "bank_evaluator", "bank_owner"), (False, False, False, False))
    assert revision == migrate.head_revision()
    assert foreign_tables == 0


async def test_forced_rls_binds_the_owner_outside_its_seed_context(production_postgres: PostgresInstance) -> None:
    owner = owner_engine(production_postgres)
    try:
        async with owner.begin() as connection:
            without = int((await connection.execute(text("SELECT count(*) FROM app.customers"))).scalar_one())
            await connection.execute(text("SELECT set_config('app.role', 'seed', true)"))
            seeded = int((await connection.execute(text("SELECT count(*) FROM app.customers"))).scalar_one())
            runtime = await connection.execute(text("SELECT count(*) FROM app.conversations"))
            conversations = int(runtime.scalar_one())
    finally:
        await owner.dispose()
    assert without == 0
    assert seeded == len(scenario_data().customers)
    assert conversations == 0  # the seed context never reaches runtime tables


async def test_the_audit_replay_check_reads_digests_under_the_non_superuser_owner(
    production_postgres: PostgresInstance, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _chat(production_postgres, monkeypatch)
    owner, application = owner_engine(production_postgres), app_engine(production_postgres)
    try:
        async with owner.connect() as connection:
            stored = (await connection.execute(text("SELECT event_id, content_digest FROM app.audit_events"))).first()
        assert stored is not None
        async with application.connect() as connection:
            digest = await connection.execute(text("SELECT app.audit_event_digest(:id)"), {"id": stored.event_id})
            checked = str(digest.scalar_one())
    finally:
        await owner.dispose()
        await application.dispose()
    assert checked == stored.content_digest


async def test_the_api_and_the_shared_rate_limits_run_on_the_production_roles(
    production_postgres: PostgresInstance, monkeypatch: pytest.MonkeyPatch
) -> None:
    replies = await _chat(production_postgres, monkeypatch)
    assert replies == [200]
    engine = app_engine(production_postgres)
    try:
        store = PostgresRateLimitStore(engine, FixedClock(NOW), rate_limit_key(secrets.token_bytes(32)))
        first, second = await store.hit("auth:ip:192.0.2.9", 1), await store.hit("auth:ip:192.0.2.9", 1)
        assert (first, second is not None) == (None, True)
    finally:
        await engine.dispose()


async def test_the_retention_purge_runs_under_the_non_superuser_owner(
    production_postgres: PostgresInstance, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _chat(production_postgres, monkeypatch)
    owner, application = owner_engine(production_postgres), app_engine(production_postgres)
    try:
        async with application.begin() as connection:  # a message as the customer would write it
            await connection.execute(
                text("SELECT set_config('app.role', 'customer', true), set_config('app.customer_id', :id, true)"),
                {"id": MX},
            )
            await connection.execute(text(MESSAGE))
        report = await PostgresRetentionPurge(owner).purge(POLICY, NOW + timedelta(days=30))
        async with owner.begin() as connection:
            await connection.execute(text("SELECT set_config('app.role', 'retention', true)"))
            left = int((await connection.execute(text("SELECT count(*) FROM app.conversations"))).scalar_one())
            untouched = await connection.execute(text("DELETE FROM app.execution_records"))
            deleted_records = untouched.rowcount
    finally:
        await owner.dispose()
        await application.dispose()
    assert report.conversations >= 1
    assert report.messages >= 1
    assert report.sessions >= 1
    assert left == 0
    assert deleted_records == 0  # the retention context has no policy on execution records, so it sees none


MESSAGE = (
    "INSERT INTO app.messages (message_id, conversation_id, customer_id, sequence, sent_at, role, text) "
    "SELECT 'msg-production-' || conversation_id, conversation_id, customer_id, 99, created_at, 'user', 'fixture' "
    "FROM app.conversations ON CONFLICT DO NOTHING"
)


async def _chat(instance: PostgresInstance, monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """One signed-in turn through the real API as the application role; returns the turn statuses."""
    api_environment(monkeypatch)
    for name, value in (
        ("POSTGRES_HOST", instance.host),
        ("POSTGRES_PORT", str(instance.port)),
        ("POSTGRES_DB", instance.database),
        ("POSTGRES_APP_USER", instance.app_user),
        ("POSTGRES_APP_PASSWORD", instance.app_password),
    ):
        monkeypatch.setenv(name, value)
    harness = build_api(clock=FixedClock(NOW))
    try:
        async with ApiClient(harness.app) as client:
            await client.login("persona-mx")
            conversation = await client.open_conversation()
            return [(await client.say(conversation, "¿Cuál es el saldo de mis cuentas?")).status_code]
    finally:
        await harness.container.aclose()
