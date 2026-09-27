from datetime import timedelta

import pytest

from bank_agent.domain.complaint import Priority
from bank_agent.domain.errors import (
    AccessContextError,
    DuplicateEntityError,
    HandoffNotFoundError,
    InvalidHandoffTransitionError,
)
from bank_agent.domain.handoff import EscalationReasonCode, HandoffOutcomeCode, HandoffStatus
from bank_agent.domain.identifiers import HandoffId
from bank_agent.domain.locale import Language
from bank_agent.ports.repositories.handoffs import HandoffQuery
from bank_agent_builders import T0, handoff
from bank_agent_contracts import AGENT, CONTEXT_A, CONTEXT_B, EVALUATOR, WriteBackend

FIRST = HandoffId("ho-000001")
SECOND = HandoffId("ho-000002")


async def _seed(backend: WriteBackend) -> None:
    async with backend.uow_factory()(CONTEXT_A) as uow:
        await uow.handoffs.add(handoff())
        await uow.handoffs.add(
            handoff(
                handoff_id=SECOND,
                language=Language.PT,
                priority=Priority.LOW,
                sla_due=T0 + timedelta(hours=2),
                escalation_reason={"code": "human_requested", "detail": "Asked for a person."},
            )
        )
        await uow.commit()


class TestHandoffRepositoryContract:
    async def test_adds_idempotently_and_rejects_a_different_document(self, write_backend: WriteBackend) -> None:
        await _seed(write_backend)
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            again = await uow.handoffs.add(handoff())
            assert again.status is HandoffStatus.OPEN
            with pytest.raises(DuplicateEntityError):
                await uow.handoffs.add(handoff(priority=Priority.CRITICAL))

    async def test_customers_see_only_their_own_handoffs(self, write_backend: WriteBackend) -> None:
        await _seed(write_backend)
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            assert await uow.handoffs.get(FIRST) is not None
        async with write_backend.uow_factory()(CONTEXT_B) as uow:
            assert await uow.handoffs.get(FIRST) is None
            with pytest.raises(AccessContextError):
                await uow.handoffs.add(handoff())
            with pytest.raises(AccessContextError):
                await uow.handoffs.list(HandoffQuery())

    async def test_agents_list_with_filters_ordered_by_sla(self, write_backend: WriteBackend) -> None:
        await _seed(write_backend)
        async with write_backend.uow_factory()(AGENT) as uow:
            everything = await uow.handoffs.list(HandoffQuery())
            assert [r.handoff_id for r in everything] == [SECOND, FIRST]
            portuguese = await uow.handoffs.list(HandoffQuery(languages=(Language.PT,)))
            assert [r.handoff_id for r in portuguese] == [SECOND]
            high = await uow.handoffs.list(HandoffQuery(priorities=(Priority.HIGH,)))
            assert [r.handoff_id for r in high] == [FIRST]
            legal = await uow.handoffs.list(HandoffQuery(reasons=(EscalationReasonCode.LEGAL_OR_REGULATOR_MENTION,)))
            assert [r.handoff_id for r in legal] == [FIRST]
            due_soon = await uow.handoffs.list(HandoffQuery(sla_due_before=T0 + timedelta(hours=3)))
            assert [r.handoff_id for r in due_soon] == [SECOND]
            assert await uow.handoffs.list(HandoffQuery(statuses=(HandoffStatus.RESOLVED,))) == []
            assert len(await uow.handoffs.list(HandoffQuery(limit=1))) == 1

    async def test_agent_claims_and_resolves(self, write_backend: WriteBackend) -> None:
        await _seed(write_backend)
        async with write_backend.uow_factory()(AGENT) as uow:
            claimed = await uow.handoffs.claim(FIRST, at=T0)
            assert claimed.claimed_by == AGENT.staff_id
            resolved = await uow.handoffs.resolve(
                FIRST, outcome=HandoffOutcomeCode.RESOLVED_BY_AGENT, note="Confirmed.", at=T0
            )
            await uow.commit()
        assert resolved.status is HandoffStatus.RESOLVED
        async with write_backend.uow_factory()(AGENT) as uow:
            stored = await uow.handoffs.get(FIRST)
            assert stored is not None
            assert stored.status is HandoffStatus.RESOLVED
            assert stored.handoff == handoff()

    async def test_illegal_moves_and_unknown_ids(self, write_backend: WriteBackend) -> None:
        await _seed(write_backend)
        async with write_backend.uow_factory()(AGENT) as uow:
            with pytest.raises(InvalidHandoffTransitionError):
                await uow.handoffs.resolve(FIRST, outcome=HandoffOutcomeCode.OTHER, note="", at=T0)
            with pytest.raises(HandoffNotFoundError):
                await uow.handoffs.claim(HandoffId("ho-999999"), at=T0)

    async def test_only_agents_claim(self, write_backend: WriteBackend) -> None:
        await _seed(write_backend)
        for context in (CONTEXT_A, EVALUATOR):
            async with write_backend.uow_factory()(context) as uow:
                with pytest.raises(AccessContextError):
                    await uow.handoffs.claim(FIRST, at=T0)
        async with write_backend.uow_factory()(EVALUATOR) as uow:
            with pytest.raises(AccessContextError):
                await uow.handoffs.get(FIRST)
