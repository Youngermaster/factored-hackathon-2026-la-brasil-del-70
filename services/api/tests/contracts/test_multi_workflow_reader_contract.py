"""Reader behavior added in phase 02b: product balance fields and the transaction type filter."""

from decimal import Decimal

from bank_agent.domain.identifiers import ProductId
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.transaction import TransactionType
from bank_agent.ports.repositories.transactions import TransactionQuery
from bank_agent_contracts import CONTEXT_A, ReadBackend


class TestProductBalanceReaderContract:
    async def test_returns_the_optional_balance_fields(self, read_backend: ReadBackend) -> None:
        async with read_backend.readers(CONTEXT_A) as readers:
            card = await readers.products.get(ProductId("PRD-A-CARD"))
            debit = await readers.products.get(ProductId("PRD-A-DEBIT"))
        assert card is not None
        assert card.current_balance == Money.of("8450.00", Currency.MXN)
        assert card.credit_limit == Money.of("20000.00", Currency.MXN)
        assert card.annual_interest_rate == Decimal("45.00")
        assert card.balance_as_of is not None
        assert card.days_past_due == 0
        assert debit is not None
        assert debit.current_balance is None


class TestTransactionTypeFilterContract:
    async def test_filters_by_transaction_type(self, read_backend: ReadBackend) -> None:
        payments = TransactionQuery(types=(TransactionType.PAYMENT, TransactionType.TRANSFER))
        async with read_backend.readers(CONTEXT_A) as readers:
            found = await readers.transactions.list(payments)
            everything = await readers.transactions.list(TransactionQuery())
        assert [txn.transaction_id for txn in found] == ["TXN-A-0004", "TXN-A-0005"]
        assert len(everything) == 8
