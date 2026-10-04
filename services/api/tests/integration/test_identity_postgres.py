"""The one-time code lifecycle and server-side sessions against PostgreSQL."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta

import pytest
from sqlalchemy import text

from bank_agent.adapters.identity.codes import IdentityKeys
from bank_agent.adapters.identity.provider import MockIdentityProvider
from bank_agent.adapters.identity.sender import DemoOtpSender
from bank_agent.adapters.persistence.postgres.audit import PostgresStandaloneAuditLog
from bank_agent.adapters.persistence.postgres.challenges import PostgresChallengeStore
from bank_agent.adapters.persistence.postgres.database import DatabaseRole, open_transaction
from bank_agent.adapters.persistence.postgres.seed import IdentityEntry, PostgresSeeder, SeedBundle, StaffEntry
from bank_agent.adapters.persistence.postgres.sessions import PostgresSessionStore
from bank_agent.application.identity.sessions import IssuedSession, SessionService
from bank_agent.domain.access import Role
from bank_agent.domain.errors import (
    IdentityChallengeExpiredError,
    IdentityChallengeFailedError,
    IdentityLockedError,
    SessionExpiredError,
    SessionNotFoundError,
    SessionRevokedError,
)
from bank_agent.domain.identifiers import ChallengeId, PersonaId
from bank_agent.domain.identity import DocumentIdentification, OtpChallenge, PersonaIdentification
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.ids import SequentialIdGenerator
from bank_agent_builders import T0, customer
from bank_agent_postgres import app_engine, owner_engine, reset_database
from bank_agent_test_support import PostgresInstance

KEYS = IdentityKeys(b"integration-secret-" + b"k" * 32)
PERSONA = PersonaIdentification(persona_id=PersonaId("persona-acc-mx"))


@dataclass
class Identity:
    clock: FixedClock
    provider: MockIdentityProvider
    service: SessionService


@pytest.fixture
async def identity(migrated_postgres: PostgresInstance) -> AsyncIterator[Identity]:
    await reset_database(migrated_postgres)
    owner = owner_engine(migrated_postgres)
    await PostgresSeeder(owner).load(
        SeedBundle(
            customers=(customer(),),
            identities=(
                IdentityEntry(
                    customer_id="CUS-A-0001",
                    persona_id="persona-acc-mx",
                    document_lookup=KEYS.document_lookup("MX1234567"),
                    phone_last4_lookup=KEYS.phone_lookup("CUS-A-0001", "9876"),
                ),
            ),
            staff=(StaffEntry(staff_id="agent-0001", role="agent", persona_id="persona-agent", display_name="Agent"),),
        )
    )
    await owner.dispose()
    engine = app_engine(migrated_postgres)
    clock, ids = FixedClock(T0), SequentialIdGenerator()
    provider = MockIdentityProvider(
        store=PostgresChallengeStore(engine),
        sender=DemoOtpSender(demo_mode=True, emit=lambda name, fields: None),
        keys=KEYS,
        clock=clock,
        ids=ids,
    )
    service = SessionService(
        identity=provider,
        store=PostgresSessionStore(engine),
        audit=PostgresStandaloneAuditLog(engine),
        clock=clock,
        ids=ids,
    )
    yield Identity(clock=clock, provider=provider, service=service)
    await engine.dispose()


def _code(challenge: OtpChallenge) -> str:
    assert challenge.delivery.demo_code is not None
    return challenge.delivery.demo_code


def _wrong(challenge: OtpChallenge) -> str:
    return f"{(int(_code(challenge)) + 1) % 1_000_000:06d}"


async def _login(identity: Identity) -> IssuedSession:
    challenge = await identity.service.start_login(PERSONA)
    return await identity.service.complete_login(challenge.challenge_id, _code(challenge))


async def test_personas_documents_and_staff_log_in(identity: Identity) -> None:
    assert (await _login(identity)).session.customer_id == "CUS-A-0001"
    by_document = await identity.provider.start(
        DocumentIdentification(document_number="MX-1234567", phone_last4="9876")
    )
    assert (await identity.provider.verify(by_document.challenge_id, _code(by_document))).customer_id == "CUS-A-0001"
    agent = await identity.provider.start(PersonaIdentification(persona_id=PersonaId("persona-agent")))
    assert (await identity.provider.verify(agent.challenge_id, _code(agent))).role is Role.AGENT


@pytest.mark.parametrize("swap", [False, True])
async def test_seed_reassigns_personas_without_removing_identity_rows(
    migrated_postgres: PostgresInstance, swap: bool
) -> None:
    await reset_database(migrated_postgres)
    owner = owner_engine(migrated_postgres)

    def entry(customer_id: str, persona: str | None) -> IdentityEntry:
        return IdentityEntry(
            customer_id=customer_id,
            persona_id=persona,
            document_lookup=KEYS.document_lookup(customer_id),
            phone_last4_lookup=KEYS.phone_lookup(customer_id, "9876"),
        )

    try:
        await PostgresSeeder(owner).load(
            SeedBundle(
                customers=(customer(), customer("CUS-B-0002"), customer("CUS-C-0003")),
                identities=(
                    entry("CUS-A-0001", "persona-a"),
                    entry("CUS-B-0002", "persona-b" if swap else None),
                    entry("CUS-C-0003", "persona-c"),
                ),
            )
        )
        bundle = SeedBundle(
            identities=(
                (entry("CUS-A-0001", "persona-b"), entry("CUS-B-0002", "persona-a"))
                if swap
                else (entry("CUS-B-0002", "persona-a"),)
            )
        )
        for _ in range(2):
            await PostgresSeeder(owner).load(bundle)
            async with open_transaction(owner, DatabaseRole.SEED) as connection:
                rows = (
                    await connection.execute(
                        text("SELECT customer_id, persona_id, document_lookup FROM app.identity_directory")
                    )
                ).all()
            assert {row.customer_id: row.persona_id for row in rows} == {
                "CUS-A-0001": "persona-b" if swap else None,
                "CUS-B-0002": "persona-a",
                "CUS-C-0003": "persona-c",
            }
            assert all(row.document_lookup == KEYS.document_lookup(row.customer_id) for row in rows)
    finally:
        await owner.dispose()


async def test_wrong_codes_expiry_lockout_and_cooldown(identity: Identity) -> None:
    challenge = await identity.provider.start(PERSONA)
    with pytest.raises(IdentityChallengeFailedError):
        await identity.provider.verify(challenge.challenge_id, _wrong(challenge))
    for _ in range(3):
        with pytest.raises(IdentityChallengeFailedError):
            await identity.provider.verify(challenge.challenge_id, _wrong(challenge))
    with pytest.raises(IdentityLockedError):
        await identity.provider.verify(challenge.challenge_id, _wrong(challenge))
    with pytest.raises(IdentityLockedError):
        await identity.provider.start(PERSONA)
    identity.clock.advance(timedelta(minutes=15))
    late = await identity.provider.start(PERSONA)
    identity.clock.advance(timedelta(minutes=5))
    with pytest.raises(IdentityChallengeExpiredError):
        await identity.provider.verify(late.challenge_id, _code(late))
    with pytest.raises(IdentityChallengeFailedError):
        await identity.provider.verify(ChallengeId("chl-unknown"), "123456")


async def test_sessions_expire_rotate_and_revoke(identity: Identity) -> None:
    issued = await _login(identity)
    identity.clock.advance(timedelta(minutes=10))
    challenge = await identity.service.start_step_up(issued.token)
    rotated = await identity.service.complete_step_up(issued.token, challenge.challenge_id, _code(challenge))
    with pytest.raises(SessionNotFoundError):
        await identity.service.resolve(issued.token)
    assert (await identity.service.resolve(rotated.token)).step_up_valid(identity.clock.now())
    identity.clock.advance(timedelta(minutes=15))
    with pytest.raises(SessionExpiredError, match="idle"):
        await identity.service.resolve(rotated.token)
    other = await _login(identity)
    await identity.service.logout(other.token)
    with pytest.raises(SessionRevokedError):
        await identity.service.resolve(other.token)
    last = await _login(identity)
    for _ in range(5):
        identity.clock.advance(timedelta(minutes=12))
        if identity.clock.now() >= last.session.absolute_expires_at:
            break
        await identity.service.resolve(last.token)
    with pytest.raises(SessionExpiredError, match="absolute"):
        await identity.service.resolve(last.token)
