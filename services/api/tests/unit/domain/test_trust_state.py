from datetime import timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from bank_agent.domain.errors import TrustStateViolationError
from bank_agent.domain.identifiers import LineageId
from bank_agent.domain.trust import RiskTier, TrustEvent, TrustEventKind, TrustState
from bank_agent_builders import T0

LINEAGE = LineageId("lin-000001")


def event(kind: TrustEventKind, minutes: int = 0) -> TrustEvent:
    return TrustEvent(
        kind=kind,
        occurred_at=T0 + timedelta(minutes=minutes),
        detector="injection:heuristic@1",
        detail_code="pattern_match",
    )


def state_with(*kinds: TrustEventKind) -> TrustState:
    state = TrustState.empty(LINEAGE)
    for minute, kind in enumerate(kinds):
        state = state.append(event(kind, minute))
    return state


@pytest.mark.parametrize(
    ("kinds", "tier"),
    [
        ((), RiskTier.LOW),
        ((TrustEventKind.FAILED_OTP,), RiskTier.LOW),
        ((TrustEventKind.FAILED_OTP, TrustEventKind.FAILED_OTP), RiskTier.LOW),
        ((TrustEventKind.FAILED_OTP,) * 3, RiskTier.ELEVATED),
        ((TrustEventKind.INJECTION_DETECTED,), RiskTier.ELEVATED),
        ((TrustEventKind.INJECTION_DETECTED, TrustEventKind.THIRD_PARTY_ADMISSION), RiskTier.HIGH),
        ((TrustEventKind.CROSS_CUSTOMER_PROBE,), RiskTier.HIGH),
        ((TrustEventKind.FAILED_OTP,) * 3 + (TrustEventKind.IDENTITY_MISMATCH,), RiskTier.HIGH),
    ],
)
def test_derives_the_risk_tier(kinds: tuple[TrustEventKind, ...], tier: RiskTier) -> None:
    assert state_with(*kinds).risk_tier is tier


def test_append_returns_a_new_state() -> None:
    empty = TrustState.empty(LINEAGE)
    appended = empty.append(event(TrustEventKind.FAILED_OTP))
    assert empty.events == ()
    assert len(appended.events) == 1


def test_rejects_an_event_older_than_the_last_one() -> None:
    state = state_with(TrustEventKind.FAILED_OTP, TrustEventKind.FAILED_OTP)
    with pytest.raises(TrustStateViolationError):
        state.append(event(TrustEventKind.FAILED_OTP, minutes=-5))


def test_rejects_mutation() -> None:
    state = state_with(TrustEventKind.FAILED_OTP)
    with pytest.raises(ValidationError):
        state.events = ()  # type: ignore[misc]


def test_rejects_restoring_events_out_of_order() -> None:
    with pytest.raises(ValidationError):
        TrustState(
            lineage_id=LINEAGE, events=(event(TrustEventKind.FAILED_OTP, 5), event(TrustEventKind.FAILED_OTP, 1))
        )


def test_trust_events_have_no_free_text_field() -> None:
    assert set(TrustEvent.model_fields) == {"kind", "occurred_at", "turn_id", "detector", "evidence", "detail_code"}


@given(st.lists(st.sampled_from(list(TrustEventKind)), max_size=25))
def test_risk_tier_never_decreases(kinds: list[TrustEventKind]) -> None:
    state = TrustState.empty(LINEAGE)
    previous = state.risk_tier
    for minute, kind in enumerate(kinds):
        state = state.append(event(kind, minute))
        assert state.risk_tier.rank >= previous.rank
        previous = state.risk_tier
