"""Read tools over every write backend: scoped by the session, another customer's ids behave as not found."""

from datetime import date, timedelta

import pytest

from bank_agent.application.tools.views import PaymentFilter
from bank_agent.domain.accounts import PAYMENT_TYPES
from bank_agent.domain.errors import ToolArgumentError
from bank_agent.domain.identifiers import ApplicationId, CaseId, CreditProductCode, ProductId, TransactionId
from bank_agent.domain.intelligence import DateRange
from bank_agent.domain.product import ProductStatus
from bank_agent.ports.audit import AuditQuery
from bank_agent.ports.repositories.transactions import TransactionQuery
from bank_agent_builders import CUSTOMER_B, T0
from bank_agent_contracts import EVALUATOR, WriteBackend
from bank_agent_tools import tools_for


class TestReadToolsContract:
    async def test_transactions_and_products_are_scoped_by_the_session(self, write_backend: WriteBackend) -> None:
        tools = tools_for(write_backend.uow_factory())
        recent = await tools.list_recent_transactions(TransactionQuery(limit=3))
        assert [txn.transaction_id for txn in recent] == ["TXN-A-0008", "TXN-A-0007", "TXN-A-0001"]
        assert await tools.get_transaction(TransactionId("TXN-B-0001")) is None
        assert await tools.get_product_status(ProductId("PRD-B-CARD")) is None
        card = await tools.get_product_status(ProductId("PRD-A-DEBIT"))
        assert card is not None
        assert (card.status, str(card.product_ref)) == (ProductStatus.BLOCKED, "products:PRD-A-DEBIT")
        other = await tools_for(write_backend.uow_factory(), CUSTOMER_B).get_product_status(ProductId("PRD-A-CARD"))
        assert other is None

    async def test_cards_are_listed_masked_and_scoped_by_the_session(self, write_backend: WriteBackend) -> None:
        cards = await tools_for(write_backend.uow_factory()).list_my_cards()
        assert [str(card.product_ref) for card in cards] == ["products:PRD-A-CARD", "products:PRD-A-DEBIT"]
        assert [card.status for card in cards] == [ProductStatus.ACTIVE, ProductStatus.BLOCKED]
        other = await tools_for(write_backend.uow_factory(), CUSTOMER_B).list_my_cards()
        assert "products:PRD-A-CARD" not in [str(card.product_ref) for card in other]
        listed = await write_backend.audit_log(EVALUATOR).list(AuditQuery())
        assert "list_my_cards" in [event.action for event in listed]

    async def test_cases_are_scoped_by_the_session(self, write_backend: WriteBackend) -> None:
        tools = tools_for(write_backend.uow_factory())
        assert [case.case_id for case in await tools.list_my_cases()] == ["case-000001"]
        assert await tools.get_case_status(CaseId("case-000001")) is not None
        other = tools_for(write_backend.uow_factory(), CUSTOMER_B)
        assert await other.get_case_status(CaseId("case-000001")) is None
        assert await other.list_my_cases() == []

    async def test_balances_always_carry_an_as_of_instant(self, write_backend: WriteBackend) -> None:
        balances = await tools_for(write_backend.uow_factory()).list_my_balances()
        assert [str(view.product_ref) for view in balances] == ["products:PRD-A-CARD", "products:PRD-A-SAVE"]
        assert all(view.as_of == T0 - timedelta(days=10) for view in balances)
        card = balances[0]
        assert card.available_credit is not None
        assert str(card.available_credit.amount) == "11550.00"
        assert await tools_for(write_backend.uow_factory(), CUSTOMER_B).list_my_balances() == []

    async def test_payment_status_reads_only_payments_and_transfers(self, write_backend: WriteBackend) -> None:
        views = await tools_for(write_backend.uow_factory()).get_payment_status(PaymentFilter())
        assert [str(view.transaction_ref) for view in views] == ["transactions:TXN-A-0004", "transactions:TXN-A-0005"]
        assert {view.transaction_type for view in views} <= PAYMENT_TYPES
        assert await tools_for(write_backend.uow_factory(), CUSTOMER_B).get_payment_status(PaymentFilter()) == []

    async def test_statement_summaries_total_per_currency_and_cap_the_period(self, write_backend: WriteBackend) -> None:
        tools = tools_for(write_backend.uow_factory())
        period = DateRange(start=date(2026, 5, 1), end=date(2026, 6, 10))
        summary = await tools.get_statement_summary(ProductId("PRD-A-CARD"), period)
        assert summary is not None
        assert summary.transaction_count == 7
        assert summary.not_settled_count == 3
        assert all(total.debits.currency is total.currency for total in summary.totals)
        assert len({total.currency for total in summary.totals}) == len(summary.totals)
        assert summary.as_of == T0 - timedelta(days=10)
        assert await tools.get_statement_summary(ProductId("PRD-B-CARD"), period) is None
        with pytest.raises(ToolArgumentError):
            await tools.get_statement_summary(
                ProductId("PRD-A-CARD"), DateRange(start=date(2026, 1, 1), end=date(2026, 6, 1))
            )

    async def test_credit_reads_follow_the_verified_jurisdiction(self, write_backend: WriteBackend) -> None:
        tools = tools_for(write_backend.uow_factory())
        assert [p.product_code for p in await tools.list_credit_products()] == ["MX-CC-FIXTURE", "MX-PL-FIXTURE"]
        assert await tools.get_credit_product(CreditProductCode("CO-CC-FIXTURE")) is None
        assert await tools.get_credit_product(CreditProductCode("MX-PL-FIXTURE")) is not None
        assert await tools.get_credit_application_status(ApplicationId("app-000001")) is not None
        other = tools_for(write_backend.uow_factory(), CUSTOMER_B)
        assert await other.get_credit_application_status(ApplicationId("app-000001")) is None

    async def test_credit_applications_are_listed_newest_first_and_scoped_by_the_session(
        self, write_backend: WriteBackend
    ) -> None:
        mine = await tools_for(write_backend.uow_factory()).list_my_credit_applications()
        assert [item.application_id for item in mine] == ["app-000001"]
        assert await tools_for(write_backend.uow_factory(), CUSTOMER_B).list_my_credit_applications() == []
        listed = await write_backend.audit_log(EVALUATOR).list(AuditQuery())
        assert [event.action for event in listed].count("list_my_credit_applications") == 2

    async def test_every_read_is_audited_with_redacted_arguments(self, write_backend: WriteBackend) -> None:
        tools = tools_for(write_backend.uow_factory())
        await tools.get_transaction(TransactionId("TXN-A-0001"))
        await tools.get_payment_status(PaymentFilter(limit=5))
        listed = await write_backend.audit_log(EVALUATOR).list(AuditQuery())
        events = sorted(listed, key=lambda event: event.action, reverse=True)
        assert [event.action for event in events] == ["get_transaction", "get_payment_status"]
        assert events[0].arguments == {"transaction_id": "[redacted]"}
        assert str(events[0].target) == "transactions:TXN-A-0001"
        assert events[1].arguments == {"statuses": [], "limit": 5}
        assert all(event.actor_ref == "CUS-A-0001" for event in events)
