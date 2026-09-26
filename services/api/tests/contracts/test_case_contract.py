from datetime import timedelta

import pytest

from bank_agent.domain.dispute import DisputeCase, DisputeReason, DisputeStatus
from bank_agent.domain.errors import (
    AccessContextError,
    CaseNotFoundError,
    ConcurrencyConflictError,
    DuplicateEntityError,
    IdempotencyConflictError,
)
from bank_agent.domain.identifiers import CaseId, IdempotencyKey, TransactionId
from bank_agent_builders import T0, dispute_case, handoff, idempotency_key, transaction
from bank_agent_contracts import AGENT, CONTEXT_A, CONTEXT_B, EVALUATOR, WriteBackend

EXISTING = CaseId("case-000001")


def _new_case(case_id: str = "case-000002", key: str = "idem-key-fixture-0100") -> DisputeCase:
    return dispute_case(case_id, txn=transaction("TXN-A-0001"), key=key)


class TestCaseRepositoryContract:
    async def test_adds_and_reads_back_a_case(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            stored = await uow.cases.add(_new_case())
            await uow.commit()
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            assert await uow.cases.get(stored.case_id) == stored
            assert await uow.cases.find_by_idempotency_key(stored.idempotency_key) == stored

    async def test_adding_the_same_request_again_returns_the_stored_case(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            first = await uow.cases.add(_new_case())
            replay = await uow.cases.add(_new_case("case-000003"))
            await uow.commit()
        assert replay == first
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            assert len(await uow.cases.list()) == 2

    async def test_reusing_a_key_for_a_different_request_conflicts(self, write_backend: WriteBackend) -> None:
        other = dispute_case("case-000003", txn=transaction("TXN-A-0007"), key=idempotency_key("0100"))
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            await uow.cases.add(_new_case())
            with pytest.raises(IdempotencyConflictError):
                await uow.cases.add(other)
            with pytest.raises(DuplicateEntityError):
                await uow.cases.add(_new_case("case-000002", key=idempotency_key("0200")))

    async def test_cannot_add_a_case_for_another_customer(self, write_backend: WriteBackend) -> None:
        foreign = dispute_case("case-000009", txn=transaction("TXN-B-0001", customer_id="CUS-B-0002"))
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            with pytest.raises(AccessContextError):
                await uow.cases.add(foreign)

    async def test_another_customers_case_behaves_like_a_missing_one(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_B) as uow:
            assert await uow.cases.get(EXISTING) is None
            assert await uow.cases.list() == []
            assert await uow.cases.find_by_idempotency_key(IdempotencyKey("idem-key-fixture-0001")) is None
            assert await uow.cases.find_open_for_transaction(TransactionId("TXN-A-0002")) is None
            existing = dispute_case("case-000001", txn=transaction("TXN-A-0002"))
            with pytest.raises(CaseNotFoundError):
                await uow.cases.update(existing, expected_version=0)

    async def test_finds_the_open_case_for_a_transaction(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            found = await uow.cases.find_open_for_transaction(TransactionId("TXN-A-0002"))
            assert found is not None
            assert found.case_id == EXISTING
            resolved = found.transition_to(DisputeStatus.REJECTED, at=T0, reason_code="duplicate")
            await uow.cases.update(resolved, expected_version=found.version)
            assert await uow.cases.find_open_for_transaction(TransactionId("TXN-A-0002")) is None

    async def test_update_increments_the_version_and_rejects_stale_writes(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            current = await uow.cases.get(EXISTING)
            assert current is not None
            in_review = current.transition_to(DisputeStatus.IN_REVIEW, at=T0, reason_code="review")
            stored = await uow.cases.update(in_review, expected_version=current.version)
            assert stored.version == current.version + 1
            with pytest.raises(ConcurrencyConflictError):
                await uow.cases.update(in_review, expected_version=current.version)
            with pytest.raises(ConcurrencyConflictError):
                await uow.cases.update(
                    stored.evolve(idempotency_key=idempotency_key("9999")), expected_version=stored.version
                )

    async def test_lists_most_recent_first_and_filters_by_status(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            newer = await uow.cases.add(
                dispute_case("case-000005", txn=transaction("TXN-A-0007"), opened_at=T0 + timedelta(hours=1))
            )
            listed = await uow.cases.list()
            assert [case.case_id for case in listed] == [newer.case_id, EXISTING]
            assert await uow.cases.list(frozenset({DisputeStatus.RESOLVED})) == []
            assert len(await uow.cases.list(limit=1)) == 1

    async def test_agents_read_only_cases_referenced_by_a_handoff(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(AGENT) as uow:
            assert await uow.cases.get(EXISTING) is None
            with pytest.raises(AccessContextError):
                await uow.cases.list()
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            await uow.handoffs.add(handoff(case_ref=EXISTING))
            await uow.commit()
        async with write_backend.uow_factory()(AGENT) as uow:
            case = await uow.cases.get(EXISTING)
            assert case is not None
            assert case.reason is DisputeReason.UNRECOGNIZED

    async def test_evaluators_cannot_use_the_case_repository(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(EVALUATOR) as uow:
            with pytest.raises(AccessContextError):
                await uow.cases.get(EXISTING)
            with pytest.raises(AccessContextError):
                await uow.cases.update(dispute_case(), expected_version=0)
