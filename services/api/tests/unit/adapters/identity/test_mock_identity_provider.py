from datetime import timedelta

import pytest

from bank_agent.adapters.identity.codes import IdentityKeys
from bank_agent.adapters.identity.provider import MockIdentityProvider
from bank_agent.adapters.identity.sender import DemoOtpSender
from bank_agent.adapters.identity.store import InMemoryChallengeStore, Subject
from bank_agent.domain.access import Role
from bank_agent.domain.errors import IdentityChallengeExpiredError, IdentityChallengeFailedError, IdentityLockedError
from bank_agent.domain.identifiers import ChallengeId, PersonaId
from bank_agent.domain.identity import DocumentIdentification, OtpChallenge, PersonaIdentification
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.ids import SequentialIdGenerator
from bank_agent_builders import T0, session

KEYS = IdentityKeys(b"fixture-secret-" + b"y" * 32)


def _provider(clock: FixedClock) -> MockIdentityProvider:
    store = InMemoryChallengeStore(
        personas={
            "persona-acc-mx": Subject(customer_id="CUS-A-0001"),
            "persona-agent": Subject(staff_id="agent-0001", staff_role="agent"),
        },
        documents={KEYS.document_lookup("MX1234567"): ("CUS-A-0001", KEYS.phone_lookup("CUS-A-0001", "9876"))},
    )
    return MockIdentityProvider(
        store=store,
        sender=DemoOtpSender(demo_mode=True, emit=lambda name, fields: None),
        keys=KEYS,
        clock=clock,
        ids=SequentialIdGenerator(),
    )


def _code(challenge: OtpChallenge) -> str:
    assert challenge.delivery.demo_code is not None
    return challenge.delivery.demo_code


def _wrong(code: str) -> str:
    return f"{(int(code) + 1) % 1_000_000:06d}"


async def test_a_persona_verifies_with_the_delivered_code() -> None:
    provider = _provider(FixedClock(T0))
    challenge = await provider.start(PersonaIdentification(persona_id=PersonaId("persona-acc-mx")))
    identity = await provider.verify(challenge.challenge_id, _code(challenge))
    expected = (Role.CUSTOMER, "CUS-A-0001", "otp_verified")
    assert (identity.role, identity.customer_id, identity.auth_level.value) == expected
    with pytest.raises(IdentityChallengeFailedError):
        await provider.verify(challenge.challenge_id, _code(challenge))


async def test_a_document_needs_the_matching_phone_digits() -> None:
    provider = _provider(FixedClock(T0))
    good = await provider.start(DocumentIdentification(document_number="mx-1234567", phone_last4="9876"))
    assert (await provider.verify(good.challenge_id, _code(good))).customer_id == "CUS-A-0001"
    bad = await provider.start(DocumentIdentification(document_number="MX1234567", phone_last4="0000"))
    with pytest.raises(IdentityChallengeFailedError) as failure:
        await provider.verify(bad.challenge_id, _code(bad))
    assert str(failure.value) == str(IdentityChallengeFailedError())


async def test_an_unknown_person_gets_the_same_challenge_and_the_same_error() -> None:
    provider = _provider(FixedClock(T0))
    known = await provider.start(PersonaIdentification(persona_id=PersonaId("persona-acc-mx")))
    unknown = await provider.start(PersonaIdentification(persona_id=PersonaId("persona-nobody")))
    assert known.model_dump(exclude={"challenge_id", "delivery"}) == unknown.model_dump(
        exclude={"challenge_id", "delivery"}
    )
    assert unknown.delivery.channel == known.delivery.channel
    with pytest.raises(IdentityChallengeFailedError) as unknown_error:
        await provider.verify(unknown.challenge_id, _code(unknown))
    with pytest.raises(IdentityChallengeFailedError) as wrong_error:
        await provider.verify(known.challenge_id, _wrong(_code(known)))
    assert str(unknown_error.value) == str(wrong_error.value)
    with pytest.raises(IdentityChallengeFailedError):
        await provider.verify(ChallengeId("chl-missing"), "123456")


async def test_codes_expire_after_five_minutes() -> None:
    clock = FixedClock(T0)
    provider = _provider(clock)
    challenge = await provider.start(PersonaIdentification(persona_id=PersonaId("persona-acc-mx")))
    assert challenge.expires_at == T0 + timedelta(minutes=5)
    clock.advance(timedelta(minutes=5))
    with pytest.raises(IdentityChallengeExpiredError):
        await provider.verify(challenge.challenge_id, _code(challenge))


async def test_five_wrong_codes_lock_the_subject_until_the_cooldown_passes() -> None:
    clock = FixedClock(T0)
    provider = _provider(clock)
    persona = PersonaIdentification(persona_id=PersonaId("persona-acc-mx"))
    challenge = await provider.start(persona)
    for _ in range(4):
        with pytest.raises(IdentityChallengeFailedError):
            await provider.verify(challenge.challenge_id, _wrong(_code(challenge)))
    with pytest.raises(IdentityLockedError) as locked:
        await provider.verify(challenge.challenge_id, _wrong(_code(challenge)))
    assert locked.value.retry_after == timedelta(minutes=15)
    with pytest.raises(IdentityLockedError):
        await provider.verify(challenge.challenge_id, _code(challenge))
    with pytest.raises(IdentityLockedError):
        await provider.start(persona)
    clock.advance(timedelta(minutes=15))
    with pytest.raises(IdentityChallengeFailedError):
        await provider.verify(challenge.challenge_id, _code(challenge))
    fresh = await provider.start(persona)
    assert (await provider.verify(fresh.challenge_id, _code(fresh))).customer_id == "CUS-A-0001"


async def test_staff_personas_verify_with_their_role() -> None:
    provider = _provider(FixedClock(T0))
    challenge = await provider.start(PersonaIdentification(persona_id=PersonaId("persona-agent")))
    identity = await provider.verify(challenge.challenge_id, _code(challenge))
    assert (identity.role, identity.staff_id) == (Role.AGENT, "agent-0001")


async def test_step_up_is_bound_to_its_session_and_opens_a_five_minute_window() -> None:
    clock = FixedClock(T0)
    provider = _provider(clock)
    current = session()
    challenge = await provider.start_step_up(current)
    with pytest.raises(IdentityChallengeFailedError):
        await provider.verify_step_up(session("ses-000002"), challenge.challenge_id, _code(challenge))
    with pytest.raises(IdentityChallengeFailedError):
        await provider.verify(challenge.challenge_id, _code(challenge))
    assert await provider.verify_step_up(current, challenge.challenge_id, _code(challenge)) == T0 + timedelta(minutes=5)
