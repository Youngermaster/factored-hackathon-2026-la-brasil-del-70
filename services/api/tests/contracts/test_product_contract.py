import pytest

from bank_agent.domain.errors import (
    AccessContextError,
    ConcurrencyConflictError,
    InvalidProductStateError,
    ProductNotFoundError,
)
from bank_agent.domain.identifiers import ProductId
from bank_agent.domain.product import Product, ProductStatus, ProductType
from bank_agent_contracts import AGENT, CONTEXT_A, CONTEXT_B, ReadBackend, WriteBackend

CARD_A = ProductId("PRD-A-CARD")
CARD_B = ProductId("PRD-B-CARD")


class TestProductReaderContract:
    async def test_gets_own_products(self, read_backend: ReadBackend) -> None:
        async with read_backend.readers(CONTEXT_A) as readers:
            card = await readers.products.get(CARD_A)
        assert isinstance(card, Product)
        assert card.masked_number.last4 == "1234"

    async def test_another_customers_product_behaves_like_a_missing_one(self, read_backend: ReadBackend) -> None:
        async with read_backend.readers(CONTEXT_A) as readers:
            assert await readers.products.get(CARD_B) is None
            assert await readers.products.get(ProductId("PRD-NOPE")) is None

    async def test_lists_own_products_ordered_and_filtered(self, read_backend: ReadBackend) -> None:
        async with read_backend.readers(CONTEXT_A) as readers:
            everything = await readers.products.list()
            cards = await readers.products.list(frozenset({ProductType.CREDIT_CARD, ProductType.DEBIT_CARD}))
        assert [p.product_id for p in everything] == ["PRD-A-CARD", "PRD-A-DEBIT", "PRD-A-SAVE"]
        assert [p.product_id for p in cards] == ["PRD-A-CARD", "PRD-A-DEBIT"]

    async def test_staff_context_is_refused(self, read_backend: ReadBackend) -> None:
        async with read_backend.readers(AGENT) as readers:
            with pytest.raises(AccessContextError):
                await readers.products.list()


class TestProductRepositoryContract:
    async def test_blocks_a_card_with_compare_and_set(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            blocked = await uow.products.update_status(CARD_A, ProductStatus.BLOCKED, expected=ProductStatus.ACTIVE)
            await uow.commit()
        assert blocked.status is ProductStatus.BLOCKED
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            stored = await uow.products.get(CARD_A)
            assert stored is not None
            assert stored.status is ProductStatus.BLOCKED
            again = await uow.products.update_status(CARD_A, ProductStatus.BLOCKED, expected=ProductStatus.BLOCKED)
            assert again.status is ProductStatus.BLOCKED

    async def test_stale_expected_status_conflicts(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            with pytest.raises(ConcurrencyConflictError):
                await uow.products.update_status(CARD_A, ProductStatus.BLOCKED, expected=ProductStatus.BLOCKED)

    async def test_cannot_block_a_non_card(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            with pytest.raises(InvalidProductStateError):
                await uow.products.update_status(
                    ProductId("PRD-A-SAVE"), ProductStatus.BLOCKED, expected=ProductStatus.ACTIVE
                )

    async def test_other_status_changes_are_stored(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            updated = await uow.products.update_status(
                ProductId("PRD-A-DEBIT"), ProductStatus.ACTIVE, expected=ProductStatus.BLOCKED
            )
        assert updated.status is ProductStatus.ACTIVE

    async def test_another_customers_product_is_not_found(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            with pytest.raises(ProductNotFoundError):
                await uow.products.update_status(CARD_B, ProductStatus.BLOCKED, expected=ProductStatus.ACTIVE)
        async with write_backend.uow_factory()(CONTEXT_B) as uow:
            card = await uow.products.get(CARD_B)
            assert card is not None
            assert card.status is ProductStatus.ACTIVE
