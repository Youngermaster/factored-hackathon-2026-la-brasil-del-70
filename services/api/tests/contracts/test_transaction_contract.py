from datetime import timedelta
from decimal import Decimal

import pytest

from bank_agent.domain.errors import AccessContextError
from bank_agent.domain.identifiers import ProductId, TransactionId
from bank_agent.domain.transaction import Transaction, TransactionStatus
from bank_agent.ports.repositories.transactions import TransactionQuery
from bank_agent_builders import T0
from bank_agent_contracts import AGENT, CONTEXT_A, INJECTION_MERCHANT, ReadBackend


async def _ids(backend: ReadBackend, query: TransactionQuery) -> list[str]:
    async with backend.readers(CONTEXT_A) as readers:
        return [txn.transaction_id for txn in await readers.transactions.list(query)]


class TestTransactionReaderContract:
    async def test_gets_own_transaction_as_a_domain_object(self, read_backend: ReadBackend) -> None:
        async with read_backend.readers(CONTEXT_A) as readers:
            txn = await readers.transactions.get(TransactionId("TXN-A-0001"))
        assert isinstance(txn, Transaction)
        assert txn.amount.amount == Decimal("1250.00")

    async def test_another_customers_transaction_behaves_like_a_missing_one(self, read_backend: ReadBackend) -> None:
        async with read_backend.readers(CONTEXT_A) as readers:
            assert await readers.transactions.get(TransactionId("TXN-B-0001")) is None
            assert await readers.transactions.get(TransactionId("TXN-NOPE")) is None

    async def test_lists_newest_first_with_ties_broken_by_id(self, read_backend: ReadBackend) -> None:
        ids = await _ids(read_backend, TransactionQuery())
        assert ids == [
            "TXN-A-0008",
            "TXN-A-0007",
            "TXN-A-0001",
            "TXN-A-0002",
            "TXN-A-0003",
            "TXN-A-0004",
            "TXN-A-0005",
            "TXN-A-0006",
        ]

    async def test_filters_by_inclusive_window_status_product_and_amount(self, read_backend: ReadBackend) -> None:
        window = TransactionQuery(occurred_from=T0 - timedelta(days=5), occurred_to=T0 - timedelta(days=3))
        assert await _ids(read_backend, window) == ["TXN-A-0001", "TXN-A-0002", "TXN-A-0003"]
        pending = TransactionQuery(statuses=(TransactionStatus.PENDING, TransactionStatus.REVERSED))
        assert await _ids(read_backend, pending) == ["TXN-A-0004", "TXN-A-0005"]
        debit = TransactionQuery(product_ids=(ProductId("PRD-A-DEBIT"),))
        assert await _ids(read_backend, debit) == ["TXN-A-0008"]
        amounts = TransactionQuery(min_amount=Decimal("89.90"), max_amount=Decimal("300.00"))
        assert await _ids(read_backend, amounts) == ["TXN-A-0002", "TXN-A-0003", "TXN-A-0005"]

    async def test_respects_the_limit(self, read_backend: ReadBackend) -> None:
        assert await _ids(read_backend, TransactionQuery(limit=2)) == ["TXN-A-0008", "TXN-A-0007"]

    async def test_returns_untrusted_merchant_text_unchanged(self, read_backend: ReadBackend) -> None:
        async with read_backend.readers(CONTEXT_A) as readers:
            txn = await readers.transactions.get(TransactionId("TXN-A-0008"))
        assert txn is not None
        assert txn.merchant_name == INJECTION_MERCHANT

    async def test_staff_context_is_refused(self, read_backend: ReadBackend) -> None:
        async with read_backend.readers(AGENT) as readers:
            with pytest.raises(AccessContextError):
                await readers.transactions.get(TransactionId("TXN-A-0001"))
