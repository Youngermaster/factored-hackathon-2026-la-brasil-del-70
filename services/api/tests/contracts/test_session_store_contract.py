from datetime import timedelta

import pytest

from bank_agent.domain.errors import (
    DuplicateEntityError,
    InvariantViolationError,
    SessionNotFoundError,
    TrustStateViolationError,
)
from bank_agent.domain.identifiers import LineageId, SessionId
from bank_agent.domain.trust import RiskTier, TrustEvent, TrustEventKind
from bank_agent_builders import T0, session
from bank_agent_contracts import WriteBackend

DIGEST_1 = "a" * 64
DIGEST_2 = "b" * 64


def _event(kind: TrustEventKind, minutes: int) -> TrustEvent:
    return TrustEvent(
        kind=kind, occurred_at=T0 + timedelta(minutes=minutes), detector="otp:provider@1", detail_code="x"
    )


class TestSessionStoreContract:
    async def test_creates_and_finds_by_digest_and_id(self, write_backend: WriteBackend) -> None:
        store = write_backend.session_store()
        await store.create(session(), DIGEST_1)
        assert await store.get_by_token_digest(DIGEST_1) == session()
        assert await store.get(SessionId("ses-000001")) == session()
        assert await store.get_by_token_digest(DIGEST_2) is None

    async def test_rejects_a_duplicate_id_or_digest(self, write_backend: WriteBackend) -> None:
        store = write_backend.session_store()
        await store.create(session(), DIGEST_1)
        with pytest.raises(DuplicateEntityError):
            await store.create(session(), DIGEST_2)
        with pytest.raises(DuplicateEntityError):
            await store.create(session("ses-000002"), DIGEST_1)

    async def test_saves_changes_but_never_the_identity(self, write_backend: WriteBackend) -> None:
        store = write_backend.session_store()
        await store.create(session(), DIGEST_1)
        touched = session().touched(T0 + timedelta(minutes=5))
        await store.save(touched)
        assert await store.get(SessionId("ses-000001")) == touched
        with pytest.raises(InvariantViolationError):
            await store.save(touched.evolve(lineage_id="lin-other"))
        with pytest.raises(SessionNotFoundError):
            await store.save(session("ses-000009"))

    async def test_rotation_revokes_the_old_session_and_retires_its_digest(self, write_backend: WriteBackend) -> None:
        store = write_backend.session_store()
        await store.create(session(), DIGEST_1)
        rotated = session("ses-000002", created_at=T0 + timedelta(minutes=3)).evolve(lineage_id="lin-ses-000001")
        await store.rotate(SessionId("ses-000001"), rotated, DIGEST_2)
        assert await store.get_by_token_digest(DIGEST_1) is None
        assert await store.get_by_token_digest(DIGEST_2) == rotated
        old = await store.get(SessionId("ses-000001"))
        assert old is not None
        assert old.revoked_at == T0 + timedelta(minutes=3)

    async def test_rotation_keeps_the_lineage_and_subject(self, write_backend: WriteBackend) -> None:
        store = write_backend.session_store()
        await store.create(session(), DIGEST_1)
        with pytest.raises(InvariantViolationError):
            await store.rotate(SessionId("ses-000001"), session("ses-000002"), DIGEST_2)
        with pytest.raises(SessionNotFoundError):
            await store.rotate(SessionId("ses-000404"), session("ses-000002"), DIGEST_2)
        with pytest.raises(DuplicateEntityError):
            await store.rotate(SessionId("ses-000001"), session(), DIGEST_2)

    async def test_counts_only_live_sessions(self, write_backend: WriteBackend) -> None:
        store = write_backend.session_store()
        await store.create(session("ses-live-0001"), "c" * 64)
        await store.create(session("ses-idle-0001", created_at=T0 - timedelta(minutes=20)), "d" * 64)
        await store.create(session("ses-gone-0001").revoked(T0 + timedelta(minutes=1)), "e" * 64)
        await store.create(session("ses-late-0001").touched(T0 + timedelta(minutes=10)), "f" * 64)
        assert await store.count_active(T0) == 3
        assert await store.count_active(T0 + timedelta(minutes=5)) == 2
        assert await store.count_active(T0 + timedelta(minutes=20)) == 1
        assert await store.count_active(T0 + timedelta(hours=2)) == 0

    async def test_trust_state_is_append_only_per_lineage(self, write_backend: WriteBackend) -> None:
        store = write_backend.session_store()
        lineage = LineageId("lin-ses-000001")
        assert (await store.get_trust_state(lineage)).events == ()
        await store.append_trust_event(lineage, _event(TrustEventKind.INJECTION_DETECTED, 1))
        state = await store.append_trust_event(lineage, _event(TrustEventKind.THIRD_PARTY_ADMISSION, 2))
        assert state.risk_tier is RiskTier.HIGH
        assert await store.get_trust_state(lineage) == state
        assert (await store.get_trust_state(LineageId("lin-other"))).events == ()
        with pytest.raises(TrustStateViolationError):
            await store.append_trust_event(lineage, _event(TrustEventKind.FAILED_OTP, 0))
