import pytest

from bank_agent.domain.errors import ConcurrencyConflictError
from bank_agent.domain.identifiers import CaseId, ProductId
from bank_agent.domain.product import ProductStatus
from bank_agent_builders import dispute_case, idempotency_key, transaction
from bank_agent_contracts import CONTEXT_A, WriteBackend

NEW_CASE = CaseId("case-000002")


class TestUnitOfWorkContract:
    async def test_is_bound_to_its_context(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            assert uow.context == CONTEXT_A

    async def test_reads_see_their_own_writes_before_commit(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            await uow.cases.add(dispute_case("case-000002", txn=transaction("TXN-A-0001"), key=idempotency_key("0300")))
            assert await uow.cases.get(NEW_CASE) is not None
            async with write_backend.uow_factory()(CONTEXT_A) as other:
                assert await other.cases.get(NEW_CASE) is None

    async def test_leaving_without_commit_rolls_back(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            await uow.cases.add(dispute_case("case-000002", txn=transaction("TXN-A-0001"), key=idempotency_key("0300")))
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            assert await uow.cases.get(NEW_CASE) is None

    async def test_an_exception_rolls_back(self, write_backend: WriteBackend) -> None:
        async def fail_midway() -> None:
            async with write_backend.uow_factory()(CONTEXT_A) as uow:
                await uow.cases.add(
                    dispute_case("case-000002", txn=transaction("TXN-A-0001"), key=idempotency_key("0300"))
                )
                raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            await fail_midway()
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            assert await uow.cases.get(NEW_CASE) is None

    async def test_explicit_rollback_discards_writes(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            await uow.cases.add(dispute_case("case-000002", txn=transaction("TXN-A-0001"), key=idempotency_key("0300")))
            await uow.rollback()
            assert await uow.cases.get(NEW_CASE) is None

    async def test_conflicting_commits_fail_and_apply_nothing(self, write_backend: WriteBackend) -> None:
        card = ProductId("PRD-A-CARD")
        factory = write_backend.uow_factory()
        async with factory(CONTEXT_A) as first, factory(CONTEXT_A) as second:
            await first.products.update_status(card, ProductStatus.BLOCKED, expected=ProductStatus.ACTIVE)
            await second.products.update_status(card, ProductStatus.SUSPENDED, expected=ProductStatus.ACTIVE)
            await second.cases.add(
                dispute_case("case-000002", txn=transaction("TXN-A-0001"), key=idempotency_key("0300"))
            )
            await first.commit()
            with pytest.raises(ConcurrencyConflictError):
                await second.commit()
        async with factory(CONTEXT_A) as uow:
            stored = await uow.products.get(card)
            assert stored is not None
            assert stored.status is ProductStatus.BLOCKED
            assert await uow.cases.get(NEW_CASE) is None
