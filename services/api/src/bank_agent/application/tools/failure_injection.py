"""``ToolFailureInjector``: a decorator of ``SessionToolset`` for tests and evaluations only.

Modes: ``timeout``, ``transient_error``, and ``permanent_error`` raise the matching tool error before the call;
``partial_write`` runs a write through tools that never commit, so the caller gets a plausible result while the
read-back finds nothing. It refuses to be built in production.
"""

from collections.abc import Mapping, Sequence

from bank_agent.application.tools.banking import SessionToolset
from bank_agent.application.tools.context import SessionContext
from bank_agent.application.tools.views import PaymentFilter, ProductStatusView
from bank_agent.domain.accounts import BalanceView, PaymentStatusView, StatementSummary
from bank_agent.domain.actions import (
    WRITE_TOOLS,
    CreateDisputeArguments,
    SubmitCreditApplicationArguments,
    ToolFailureMode,
    ToolName,
)
from bank_agent.domain.cards import CardBlockReason, CardStatusView
from bank_agent.domain.credit import CreditApplicationIntake, CreditProduct
from bank_agent.domain.dispute import DisputeCase
from bank_agent.domain.errors import ConfigurationError, ToolPermanentError, ToolTimeoutError, ToolTransientError
from bank_agent.domain.identifiers import (
    ApplicationId,
    CaseId,
    CreditProductCode,
    IdempotencyKey,
    ProductId,
    TransactionId,
)
from bank_agent.domain.intelligence import DateRange
from bank_agent.domain.product import Product
from bank_agent.domain.transaction import Transaction
from bank_agent.ports.repositories.transactions import TransactionQuery

_RAISED = {
    ToolFailureMode.TIMEOUT: ToolTimeoutError,
    ToolFailureMode.TRANSIENT_ERROR: ToolTransientError,
    ToolFailureMode.PERMANENT_ERROR: ToolPermanentError,
}


class ToolFailureInjector:
    """Implements ``SessionToolset``. ``uncommitted`` must be the same tools built with ``commit=False``."""

    def __init__(
        self,
        inner: SessionToolset,
        uncommitted: SessionToolset,
        plan: Mapping[ToolName, ToolFailureMode],
        *,
        environment: str,
    ) -> None:
        if environment == "production":
            raise ConfigurationError("the tool failure injector is refused in production")
        partial_reads = [
            tool for tool, mode in plan.items() if mode is ToolFailureMode.PARTIAL_WRITE and tool not in WRITE_TOOLS
        ]
        if partial_reads:
            raise ConfigurationError("partial writes apply to write tools only")
        self._inner, self._uncommitted, self._plan = inner, uncommitted, dict(plan)
        self.calls: list[ToolName] = []

    @property
    def context(self) -> SessionContext:
        return self._inner.context

    def _target(self, tool: ToolName) -> SessionToolset:
        """Raise the planned error, or pick the tools a call runs on."""
        self.calls.append(tool)
        mode = self._plan.get(tool)
        if mode in _RAISED:
            raise _RAISED[mode](f"injected {mode.value} for {tool.value}")
        return self._uncommitted if mode is ToolFailureMode.PARTIAL_WRITE else self._inner

    async def list_recent_transactions(self, filters: TransactionQuery) -> Sequence[Transaction]:
        return await self._target(ToolName.LIST_RECENT_TRANSACTIONS).list_recent_transactions(filters)

    async def get_transaction(self, transaction_id: TransactionId) -> Transaction | None:
        return await self._target(ToolName.GET_TRANSACTION).get_transaction(transaction_id)

    async def get_product_status(self, product_id: ProductId) -> ProductStatusView | None:
        return await self._target(ToolName.GET_PRODUCT_STATUS).get_product_status(product_id)

    async def list_my_cards(self) -> Sequence[CardStatusView]:
        return await self._target(ToolName.LIST_MY_CARDS).list_my_cards()

    async def list_my_cases(self) -> Sequence[DisputeCase]:
        return await self._target(ToolName.LIST_MY_CASES).list_my_cases()

    async def get_case_status(self, case_id: CaseId) -> DisputeCase | None:
        return await self._target(ToolName.GET_CASE_STATUS).get_case_status(case_id)

    async def list_my_balances(self) -> Sequence[BalanceView]:
        return await self._target(ToolName.LIST_MY_BALANCES).list_my_balances()

    async def get_payment_status(self, filters: PaymentFilter) -> Sequence[PaymentStatusView]:
        return await self._target(ToolName.GET_PAYMENT_STATUS).get_payment_status(filters)

    async def get_statement_summary(self, product_id: ProductId, period: DateRange) -> StatementSummary | None:
        return await self._target(ToolName.GET_STATEMENT_SUMMARY).get_statement_summary(product_id, period)

    async def list_credit_products(self) -> Sequence[CreditProduct]:
        return await self._target(ToolName.LIST_CREDIT_PRODUCTS).list_credit_products()

    async def get_credit_product(self, code: CreditProductCode) -> CreditProduct | None:
        return await self._target(ToolName.GET_CREDIT_PRODUCT).get_credit_product(code)

    async def get_credit_application_status(self, application_id: ApplicationId) -> CreditApplicationIntake | None:
        return await self._target(ToolName.GET_CREDIT_APPLICATION_STATUS).get_credit_application_status(application_id)

    async def list_my_credit_applications(self) -> Sequence[CreditApplicationIntake]:
        return await self._target(ToolName.LIST_MY_CREDIT_APPLICATIONS).list_my_credit_applications()

    async def create_dispute_case(
        self, request: CreateDisputeArguments, idempotency_key: IdempotencyKey
    ) -> DisputeCase:
        return await self._target(ToolName.CREATE_DISPUTE_CASE).create_dispute_case(request, idempotency_key)

    async def block_card(
        self, product_id: ProductId, idempotency_key: IdempotencyKey, reason: CardBlockReason | None = None
    ) -> Product:
        return await self._target(ToolName.BLOCK_CARD).block_card(product_id, idempotency_key, reason)

    async def submit_credit_application(
        self, request: SubmitCreditApplicationArguments, idempotency_key: IdempotencyKey
    ) -> CreditApplicationIntake:
        tools = self._target(ToolName.SUBMIT_CREDIT_APPLICATION)
        return await tools.submit_credit_application(request, idempotency_key)
