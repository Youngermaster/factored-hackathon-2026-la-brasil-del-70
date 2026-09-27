from dataclasses import dataclass
from datetime import timedelta

import pytest

from bank_agent.adapters.identity.codes import IdentityKeys
from bank_agent.adapters.identity.provider import MockIdentityProvider
from bank_agent.adapters.identity.sender import DemoOtpSender
from bank_agent.adapters.identity.store import InMemoryChallengeStore, Subject
from bank_agent.adapters.persistence.memory.sessions import InMemorySessionStore
from bank_agent.adapters.persistence.memory.store import InMemoryStore
from bank_agent.adapters.persistence.memory.unit_of_work import standalone_audit_log
from bank_agent.application.identity.sessions import IssuedSession, SessionService, token_digest
from bank_agent.domain.access import AccessContext, AuthLevel, Role
from bank_agent.domain.errors import (
    IdentityChallengeFailedError,
    SessionExpiredError,
    SessionNotFoundError,
    SessionRevokedError,
)
from bank_agent.domain.identifiers import PersonaId, StaffId
from bank_agent.domain.identity import PersonaIdentification
from bank_agent.ports.audit import AuditQuery
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.ids import SequentialIdGenerator
from bank_agent_builders import T0

KEYS = IdentityKeys(b"fixture-secret-" + b"z" * 32)
PERSONA = PersonaIdentification(persona_id=PersonaId("persona-acc-mx"))


@dataclass
class Harness:
    clock: FixedClock
    store: InMemorySessionStore
    audit: InMemoryStore
    service: SessionService

    async def login(self) -> IssuedSession:
        challenge = await self.service.start_login(PERSONA)
        assert challenge.delivery.demo_code is not None
        return await self.service.complete_login(challenge.challenge_id, challenge.delivery.demo_code)

    async def step_up(self, token: str) -> IssuedSession:
        challenge = await self.service.start_step_up(token)
        assert challenge.delivery.demo_code is not None
        return await self.service.complete_step_up(token, challenge.challenge_id, challenge.delivery.demo_code)


@pytest.fixture
def harness() -> Harness:
    clock, ids, audit = FixedClock(T0), SequentialIdGenerator(), InMemoryStore()
    provider = MockIdentityProvider(
        store=InMemoryChallengeStore(personas={"persona-acc-mx": Subject(customer_id="CUS-A-0001")}),
        sender=DemoOtpSender(demo_mode=True, emit=lambda name, fields: None),
        keys=KEYS,
        clock=clock,
        ids=ids,
    )
    store = InMemorySessionStore()
    service = SessionService(identity=provider, store=store, audit=standalone_audit_log(audit), clock=clock, ids=ids)
    return Harness(clock=clock, store=store, audit=audit, service=service)


async def test_login_issues_a_256_bit_token_stored_only_as_a_digest(harness: Harness) -> None:
    issued = await harness.login()
    assert len(issued.token) >= 43
    assert "token" not in repr(issued).replace("token=<redacted>", "")
    assert await harness.store.get_by_token_digest(token_digest(issued.token)) == issued.session
    session = issued.session
    assert (session.role, session.customer_id, session.auth_level) == (
        Role.CUSTOMER,
        "CUS-A-0001",
        AuthLevel.OTP_VERIFIED,
    )
    assert session.idle_expires_at == T0 + timedelta(minutes=15)
    assert session.absolute_expires_at == T0 + timedelta(minutes=60)


async def test_activity_slides_the_idle_expiry_but_never_the_absolute_one(harness: Harness) -> None:
    issued = await harness.login()
    for _ in range(4):
        harness.clock.advance(timedelta(minutes=14))
        await harness.service.resolve(issued.token)
    harness.clock.advance(timedelta(minutes=4))
    with pytest.raises(SessionExpiredError, match="absolute"):
        await harness.service.resolve(issued.token)


async def test_a_session_idle_for_fifteen_minutes_expires(harness: Harness) -> None:
    issued = await harness.login()
    harness.clock.advance(timedelta(minutes=15))
    with pytest.raises(SessionExpiredError, match="idle"):
        await harness.service.resolve(issued.token)


async def test_step_up_rotates_the_session_and_opens_a_window(harness: Harness) -> None:
    issued = await harness.login()
    harness.clock.advance(timedelta(minutes=1))
    rotated = await harness.step_up(issued.token)
    assert rotated.session.session_id != issued.session.session_id
    assert rotated.session.lineage_id == issued.session.lineage_id
    assert rotated.session.step_up_valid(harness.clock.now())
    with pytest.raises(SessionNotFoundError):
        await harness.service.resolve(issued.token)
    harness.clock.advance(timedelta(minutes=5))
    assert not (await harness.service.resolve(rotated.token)).step_up_valid(harness.clock.now())


async def test_logout_and_revocation_end_the_session(harness: Harness) -> None:
    first, second = await harness.login(), await harness.login()
    await harness.service.logout(first.token)
    with pytest.raises(SessionRevokedError):
        await harness.service.resolve(first.token)
    await harness.service.revoke(second.session.session_id)
    with pytest.raises(SessionRevokedError):
        await harness.service.resolve(second.token)
    with pytest.raises(SessionNotFoundError):
        await harness.service.resolve("not-a-token")


async def test_failures_and_successes_are_audited_without_codes(harness: Harness) -> None:
    challenge = await harness.service.start_login(PERSONA)
    with pytest.raises(IdentityChallengeFailedError):
        await harness.service.complete_login(
            challenge.challenge_id, "000000" if challenge.delivery.demo_code != "000000" else "111111"
        )
    await harness.login()
    evaluator = AccessContext.for_staff(Role.EVALUATOR, StaffId("evaluator-0001"))
    events = await standalone_audit_log(harness.audit, evaluator).list(AuditQuery())
    assert [(event.action, event.outcome.value) for event in events] == [
        ("login_started", "success"),
        ("login_verified", "failure"),
        ("login_started", "success"),
        ("login_verified", "success"),
    ]
    assert all(str(challenge.delivery.demo_code) not in event.model_dump_json() for event in events)
