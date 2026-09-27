from datetime import timedelta

import pytest
from pydantic import ValidationError

from bank_agent.domain.access import AuthLevel, Role
from bank_agent.domain.errors import ClockRegressionError, SessionExpiredError, SessionRevokedError
from bank_agent.domain.session import ExpiryReason, Session
from bank_agent.testing.clock import FixedClock
from bank_agent_builders import T0, session

MINUTE = timedelta(minutes=1)


def test_expires_exactly_at_the_idle_boundary() -> None:
    active = session()
    assert active.expiry_reason(T0 + 15 * MINUTE - timedelta(seconds=1)) is None
    assert active.expiry_reason(T0 + 15 * MINUTE) is ExpiryReason.IDLE


def test_activity_extends_idle_expiry_but_never_past_the_absolute_expiry() -> None:
    clock = FixedClock(T0)
    current = session()
    for _ in range(5):
        clock.advance(14 * MINUTE)
        if current.is_expired(clock.now()):
            break
        current = current.touched(clock.now())
    assert current.idle_expires_at <= current.absolute_expires_at
    assert current.expiry_reason(T0 + 60 * MINUTE) is ExpiryReason.ABSOLUTE


def test_touching_an_expired_session_raises_with_the_reason() -> None:
    with pytest.raises(SessionExpiredError) as idle:
        session().touched(T0 + 20 * MINUTE)
    assert idle.value.reason == "idle"
    kept_alive = session().touched(T0 + 14 * MINUTE).touched(T0 + 28 * MINUTE).touched(T0 + 42 * MINUTE)
    with pytest.raises(SessionExpiredError) as absolute:
        kept_alive.touched(T0 + 56 * MINUTE).touched(T0 + 61 * MINUTE)
    assert absolute.value.reason == "absolute"


def test_rejects_an_instant_before_the_last_activity() -> None:
    with pytest.raises(ClockRegressionError):
        session().touched(T0 - MINUTE)


def test_step_up_window_raises_the_effective_level_until_it_closes() -> None:
    stepped = session().with_step_up(now=T0 + MINUTE, until=T0 + 6 * MINUTE)
    assert stepped.effective_auth_level(T0 + 2 * MINUTE) is AuthLevel.STEP_UP
    assert stepped.step_up_valid(T0 + 2 * MINUTE)
    assert stepped.effective_auth_level(T0 + 6 * MINUTE) is AuthLevel.OTP_VERIFIED
    assert not stepped.step_up_valid(T0 + 6 * MINUTE)


def test_step_up_window_is_capped_at_the_absolute_expiry() -> None:
    stepped = session().with_step_up(now=T0, until=T0 + 90 * MINUTE)
    assert stepped.step_up_expires_at == stepped.absolute_expires_at


def test_rejects_a_step_up_window_in_the_past() -> None:
    with pytest.raises(ValueError, match="future"):
        session().with_step_up(now=T0 + MINUTE, until=T0)


def test_revoked_sessions_are_expired_and_cannot_be_touched() -> None:
    revoked = session().revoked(T0 + MINUTE)
    assert revoked.revoked(T0 + 2 * MINUTE) is revoked
    assert revoked.expiry_reason(T0 + MINUTE) is ExpiryReason.REVOKED
    assert revoked.effective_auth_level(T0 + MINUTE) is AuthLevel.NONE
    with pytest.raises(SessionRevokedError):
        revoked.touched(T0 + 2 * MINUTE)


def test_snapshot_and_access_context() -> None:
    active = session()
    snapshot = active.snapshot(T0 + MINUTE)
    assert snapshot.effective_auth_level is AuthLevel.OTP_VERIFIED
    assert not snapshot.expired
    assert snapshot.expiry_reason is None
    context = active.access_context()
    assert context.customer_id == active.customer_id
    assert context.session_id == active.session_id


def test_staff_sessions_name_the_staff_member() -> None:
    agent = session(customer_id=None, role=Role.AGENT, staff_id="agent-1")
    assert agent.access_context().staff_id == "agent-1"


@pytest.mark.parametrize(
    "overrides",
    [
        {"auth_level": AuthLevel.STEP_UP},
        {"idle_timeout": timedelta(0)},
        {"absolute_expires_at": T0},
        {"last_seen_at": T0 - MINUTE},
        {"customer_id": None},
    ],
)
def test_rejects_inconsistent_sessions(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Session.model_validate({**dict(session()), **overrides})
