"""The banking toolbox: session tools for the workflow, and engine-only tools no allowlist can reach.

``BankingTools.for_session(context)`` binds every tool to one validated session; no tool method accepts a
customer identifier. ``get_my_credit_profile`` lives on ``EngineOnlyTools`` so it can never appear on a per-state
tool allowlist that model output influences, and its result is never rendered or sent to a model.
"""

from collections.abc import Sequence
from typing import Protocol

from bank_agent.application.tools.base import ToolCalls, ToolDependencies
from bank_agent.application.tools.context import SessionContext
from bank_agent.application.tools.reads import ReadTools
from bank_agent.application.tools.views import PaymentFilter, ProductStatusView
from bank_agent.application.tools.writes import WriteTools
from bank_agent.domain.accounts import BalanceView, PaymentStatusView, StatementSummary
from bank_agent.domain.actions import CreateDisputeArguments, SubmitCreditApplicationArguments, ToolName
from bank_agent.domain.cards import CardBlockReason
from bank_agent.domain.credit import CreditApplicationIntake, CreditProduct, CreditProfile
from bank_agent.domain.dispute import DisputeCase
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
from bank_agent.ports.unit_of_work import UnitOfWork


class SessionToolset(Protocol):
    """The tools a workflow may call, bound to one session. Decorators (the failure injector) implement it too."""

    @property
    def context(self) -> SessionContext: ...

    async def list_recent_transactions(self, filters: TransactionQuery) -> Sequence[Transaction]: ...
    async def get_transaction(self, transaction_id: TransactionId) -> Transaction | None: ...
    async def get_product_status(self, product_id: ProductId) -> ProductStatusView | None: ...
    async def list_my_cases(self) -> Sequence[DisputeCase]: ...
    async def get_case_status(self, case_id: CaseId) -> DisputeCase | None: ...
    async def list_my_balances(self) -> Sequence[BalanceView]: ...
    async def get_payment_status(self, filters: PaymentFilter) -> Sequence[PaymentStatusView]: ...
    async def get_statement_summary(self, product_id: ProductId, period: DateRange) -> StatementSummary | None: ...
    async def list_credit_products(self) -> Sequence[CreditProduct]: ...
    async def get_credit_product(self, code: CreditProductCode) -> CreditProduct | None: ...
    async def get_credit_application_status(self, application_id: ApplicationId) -> CreditApplicationIntake | None: ...
    async def create_dispute_case(
        self, request: CreateDisputeArguments, idempotency_key: IdempotencyKey
    ) -> DisputeCase: ...
    async def block_card(
        self, product_id: ProductId, idempotency_key: IdempotencyKey, reason: CardBlockReason | None = None
    ) -> Product: ...
    async def submit_credit_application(
        self, request: SubmitCreditApplicationArguments, idempotency_key: IdempotencyKey
    ) -> CreditApplicationIntake: ...


class SessionTools(ReadTools, WriteTools):
    """Implements ``SessionToolset``."""


class EngineOnlyTools(ToolCalls):
    """Tools for the deterministic engine only (risk features and the eligibility request)."""

    async def get_my_credit_profile(self) -> CreditProfile | None:
        async def work(uow: UnitOfWork) -> CreditProfile | None:
            return await uow.credit_profiles.get_mine()

        return await self._run(ToolName.GET_MY_CREDIT_PROFILE, work)


class BankingTools:
    def __init__(self, deps: ToolDependencies) -> None:
        self._deps = deps

    def for_session(self, context: SessionContext, *, commit: bool = True) -> SessionTools:
        """Tools bound to ``context``. ``commit=False`` only backs the test and evaluation failure injector."""
        return SessionTools(self._deps, context, commit=commit)

    def engine_only(self, context: SessionContext) -> EngineOnlyTools:
        return EngineOnlyTools(self._deps, context)

    @property
    def dependencies(self) -> ToolDependencies:
        return self._deps
