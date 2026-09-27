"""Read tools. Scoped by the session: another customer's id behaves exactly like an unknown one (``None``)."""

from collections.abc import Sequence
from datetime import UTC, datetime, time

from bank_agent.application.tools.base import ToolCalls
from bank_agent.application.tools.views import PaymentFilter, ProductStatusView
from bank_agent.domain.accounts import PAYMENT_TYPES, BalanceView, PaymentStatusView, StatementPeriod, StatementSummary
from bank_agent.domain.actions import ToolName
from bank_agent.domain.cards import CardStatusView
from bank_agent.domain.credit import CreditApplicationIntake, CreditProduct
from bank_agent.domain.dispute import DisputeCase
from bank_agent.domain.errors import ToolArgumentError
from bank_agent.domain.identifiers import (
    ApplicationId,
    CaseId,
    CreditProductCode,
    ProductId,
    SourceRef,
    SourceTable,
    TransactionId,
)
from bank_agent.domain.intelligence import DateRange
from bank_agent.domain.product import CARD_TYPES, Product
from bank_agent.domain.transaction import Transaction
from bank_agent.ports.repositories.transactions import MAX_TRANSACTION_PAGE, TransactionQuery
from bank_agent.ports.unit_of_work import UnitOfWork

MAX_STATEMENT_TRANSACTIONS = 5000


def _ref(table: SourceTable, key: str | None) -> SourceRef | None:
    return SourceRef.of(table, key) if key is not None else None


async def _all_in_window(uow: UnitOfWork, product_id: ProductId, start: datetime, end: datetime) -> list[Transaction]:
    """Every transaction of the product in the window, paging newest first."""
    found: dict[str, Transaction] = {}
    upper = end
    while True:
        query = TransactionQuery(
            occurred_from=start, occurred_to=upper, product_ids=(product_id,), limit=MAX_TRANSACTION_PAGE
        )
        page = await uow.transactions.list(query)
        found.update((txn.transaction_id, txn) for txn in page)
        if len(found) > MAX_STATEMENT_TRANSACTIONS:
            raise ToolArgumentError("the statement period holds too many transactions; choose a shorter period")
        if len(page) < MAX_TRANSACTION_PAGE:
            return list(found.values())
        upper = page[-1].occurred_at


class ReadTools(ToolCalls):
    async def list_recent_transactions(self, filters: TransactionQuery) -> Sequence[Transaction]:
        async def work(uow: UnitOfWork) -> Sequence[Transaction]:
            return await uow.transactions.list(filters)

        arguments = {"statuses": filters.statuses, "types": filters.types, "limit": filters.limit}
        return await self._run(ToolName.LIST_RECENT_TRANSACTIONS, work, arguments=arguments)

    async def get_transaction(self, transaction_id: TransactionId) -> Transaction | None:
        async def work(uow: UnitOfWork) -> Transaction | None:
            return await uow.transactions.get(transaction_id)

        return await self._run(
            ToolName.GET_TRANSACTION,
            work,
            arguments={"transaction_id": transaction_id},
            target=lambda txn: _ref(SourceTable.TRANSACTIONS, txn.transaction_id if txn else None),
        )

    async def get_product_status(self, product_id: ProductId) -> ProductStatusView | None:
        async def work(uow: UnitOfWork) -> ProductStatusView | None:
            product = await uow.products.get(product_id)
            return ProductStatusView.from_product(product) if product is not None else None

        return await self._run(
            ToolName.GET_PRODUCT_STATUS,
            work,
            arguments={"product_id": product_id},
            target=lambda view: view.product_ref if view is not None else None,
        )

    async def list_my_cards(self) -> Sequence[CardStatusView]:
        """The session customer's credit and debit cards (status and expiry only), ordered by product id."""

        async def work(uow: UnitOfWork) -> Sequence[CardStatusView]:
            cards = await uow.products.list(types=CARD_TYPES)
            return [CardStatusView.from_product(card) for card in sorted(cards, key=lambda card: card.product_id)]

        return await self._run(ToolName.LIST_MY_CARDS, work)

    async def list_my_cases(self) -> Sequence[DisputeCase]:
        async def work(uow: UnitOfWork) -> Sequence[DisputeCase]:
            return await uow.cases.list()

        return await self._run(ToolName.LIST_MY_CASES, work)

    async def get_case_status(self, case_id: CaseId) -> DisputeCase | None:
        async def work(uow: UnitOfWork) -> DisputeCase | None:
            return await uow.cases.get(case_id)

        return await self._run(
            ToolName.GET_CASE_STATUS,
            work,
            arguments={"case_id": case_id},
            target=lambda case: _ref(SourceTable.DISPUTE_CASES, case.case_id if case else None),
        )

    async def list_my_balances(self) -> Sequence[BalanceView]:
        convention = self._deps.settings.balance_convention

        async def work(uow: UnitOfWork) -> Sequence[BalanceView]:
            products = await uow.products.list()
            return [BalanceView.from_product(p, convention) for p in products if p.current_balance is not None]

        return await self._run(ToolName.LIST_MY_BALANCES, work)

    async def get_payment_status(self, filters: PaymentFilter) -> Sequence[PaymentStatusView]:
        settings = self._deps.settings

        async def work(uow: UnitOfWork) -> Sequence[PaymentStatusView]:
            country = (await uow.customers.get_current()).country
            query = TransactionQuery(
                occurred_from=filters.occurred_from,
                occurred_to=filters.occurred_to,
                product_ids=filters.product_ids,
                statuses=filters.statuses,
                types=tuple(sorted(PAYMENT_TYPES)),
                min_amount=filters.min_amount,
                max_amount=filters.max_amount,
                limit=filters.limit,
            )
            products: dict[str, Product | None] = {}
            views: list[PaymentStatusView] = []
            for txn in await uow.transactions.list(query):
                if txn.product_id not in products:
                    products[txn.product_id] = await uow.products.get(txn.product_id)
                product = products[txn.product_id]
                if product is not None:
                    occurred_on = settings.local_date(country, txn.occurred_at)
                    views.append(PaymentStatusView.from_transaction(txn, product, occurred_on=occurred_on))
            return views

        return await self._run(
            ToolName.GET_PAYMENT_STATUS, work, arguments={"statuses": filters.statuses, "limit": filters.limit}
        )

    async def get_statement_summary(self, product_id: ProductId, period: DateRange) -> StatementSummary | None:
        settings = self._deps.settings
        days = (period.end - period.start).days + 1
        at = self._context.at

        async def work(uow: UnitOfWork) -> StatementSummary | None:
            if days > settings.max_statement_days:
                raise ToolArgumentError(f"a statement period covers at most {settings.max_statement_days} days")
            product = await uow.products.get(product_id)
            if product is None:
                return None
            country = (await uow.customers.get_current()).country
            zone = settings.zone(country)
            start = datetime.combine(period.start, time.min, zone).astimezone(UTC)
            end = datetime.combine(period.end, time.max, zone).astimezone(UTC)
            transactions = await _all_in_window(uow, product_id, start, end)
            return StatementSummary.from_transactions(
                StatementPeriod(product_ref=SourceRef.of(SourceTable.PRODUCTS, product_id), dates=period),
                product,
                transactions,
                as_of=product.balance_as_of or at,
                local_date=lambda instant: settings.local_date(country, instant),
            )

        return await self._run(
            ToolName.GET_STATEMENT_SUMMARY,
            work,
            arguments={"product_id": product_id, "period_days": days},
            target=lambda summary: summary.period.product_ref if summary is not None else None,
        )

    async def list_credit_products(self) -> Sequence[CreditProduct]:
        """The synthetic catalog for the verified customer's jurisdiction."""
        catalog = self._deps.catalog

        async def work(uow: UnitOfWork) -> Sequence[CreditProduct]:
            return catalog.list((await uow.customers.get_current()).country)

        return await self._run(ToolName.LIST_CREDIT_PRODUCTS, work)

    async def get_credit_product(self, code: CreditProductCode) -> CreditProduct | None:
        """A catalog entry, or ``None`` when it is unknown or offered in another jurisdiction."""
        catalog = self._deps.catalog

        async def work(uow: UnitOfWork) -> CreditProduct | None:
            product = catalog.get(code)
            country = (await uow.customers.get_current()).country
            return product if product is not None and product.jurisdiction is country else None

        return await self._run(
            ToolName.GET_CREDIT_PRODUCT,
            work,
            arguments={"product_code": code},
            target=lambda product: _ref(SourceTable.CREDIT_PRODUCTS, product.product_code if product else None),
        )

    async def get_credit_application_status(self, application_id: ApplicationId) -> CreditApplicationIntake | None:
        async def work(uow: UnitOfWork) -> CreditApplicationIntake | None:
            return await uow.credit_applications.get(application_id)

        return await self._run(
            ToolName.GET_CREDIT_APPLICATION_STATUS,
            work,
            arguments={"application_id": application_id},
            target=lambda item: _ref(SourceTable.CREDIT_APPLICATIONS, item.application_id if item else None),
        )
