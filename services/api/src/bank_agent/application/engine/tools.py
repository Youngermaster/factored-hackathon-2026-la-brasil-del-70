"""``GuardedToolset``: the only way a handler reaches a tool.

The engine sets the allowlist of the current state before each handler runs; a call outside it is recorded as
``rejected_by_allowlist`` and raises ``ToolNotAllowedError``, whatever any text says. Every call is recorded with
redacted arguments (the tools' audit allowlist), attempts, latency, and a result summary. Only transient failures
(``ToolError.retryable``) are retried, at most ``retry_budget`` times (``ESC-ALL-1``); every tool is idempotent
(reads by nature, writes by idempotency key), so a retry never duplicates an effect.
"""

import time
from collections.abc import Awaitable, Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Protocol

from bank_agent.application.engine.recorder import TurnRecorder
from bank_agent.application.tools.auditing import redact_arguments
from bank_agent.application.tools.banking import SessionToolset
from bank_agent.application.tools.views import PaymentFilter, ProductStatusView
from bank_agent.domain.accounts import BalanceView, PaymentStatusView, StatementSummary
from bank_agent.domain.actions import CreateDisputeArguments, SubmitCreditApplicationArguments, ToolName, Verification
from bank_agent.domain.cards import CardBlockReason, CardStatusView
from bank_agent.domain.credit import CreditApplicationIntake, CreditProduct, CreditProfile
from bank_agent.domain.dispute import DisputeCase
from bank_agent.domain.errors import DomainError, NotFoundError, ToolError, ToolNotAllowedError
from bank_agent.domain.execution_record import RedactedValue, ToolCallRecord, ToolCallStatus
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


def _recorded(arguments: Mapping[str, object]) -> dict[str, RedactedValue]:
    values: dict[str, RedactedValue] = {}
    for name, value in redact_arguments(arguments).items():
        if isinstance(value, list):
            values[name] = ",".join(str(item) for item in value)[:200]
        elif isinstance(value, str | int | bool) or value is None:
            values[name] = value[:200] if isinstance(value, str) else value
        else:
            values[name] = "[redacted]"
    return values


class GuardedToolset:
    def __init__(
        self,
        inner: SessionToolset,
        recorder: TurnRecorder,
        *,
        retry_budget: int,
        monotonic: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._inner = inner
        self._recorder = recorder
        self._retry_budget = retry_budget
        self._monotonic = monotonic
        self._allowed: frozenset[ToolName] = frozenset()

    @property
    def allowed(self) -> frozenset[ToolName]:
        return self._allowed

    def allow(self, tools: frozenset[ToolName]) -> None:
        self._allowed = tools

    @contextmanager
    def engine_check(self, tools: frozenset[ToolName]) -> Iterator[None]:
        """Reads the engine itself performs before routing (checking ids named in the text), in any state."""
        previous = self._allowed
        self._allowed = previous | tools
        try:
            yield
        finally:
            self._allowed = previous

    async def run[T](
        self,
        tool: ToolName,
        invoke: Callable[[], Awaitable[T]],
        *,
        arguments: Mapping[str, object] | None = None,
        idempotency_key: IdempotencyKey | None = None,
        summarize: Callable[[T], str | None] = lambda _: None,
    ) -> T:
        sequence = self._recorder.next_tool_sequence()
        recorded = _recorded(arguments or {})

        def record(status: ToolCallStatus, attempts: int, started: float, **extra: str | None) -> None:
            latency = max(0, round((self._monotonic() - started) * 1000))
            self._recorder.tool_call(
                ToolCallRecord(
                    sequence=sequence,
                    tool=tool,
                    arguments=recorded,
                    idempotency_key=idempotency_key,
                    status=status,
                    attempts=attempts,
                    latency_ms=latency,
                    error_code=extra.get("error_code"),
                    result_summary=extra.get("summary"),
                )
            )

        started = self._monotonic()
        if tool not in self._allowed:
            record(ToolCallStatus.REJECTED_BY_ALLOWLIST, 1, started, error_code=ToolNotAllowedError.code)
            self._recorder.intervention("tool_rejected_by_allowlist")
            raise ToolNotAllowedError(f"{tool.value} is not allowed in this state")
        attempts = 0
        while True:
            attempts += 1
            try:
                result = await invoke()
            except ToolError as error:
                if error.retryable and attempts <= self._retry_budget:
                    continue
                record(ToolCallStatus.FAILED, attempts, started, error_code=error.code)
                raise
            except NotFoundError as error:
                record(ToolCallStatus.NOT_FOUND, attempts, started, error_code=error.code)
                raise
            except DomainError as error:
                record(ToolCallStatus.FAILED, attempts, started, error_code=error.code)
                raise
            status = ToolCallStatus.NOT_FOUND if result is None else ToolCallStatus.OK
            record(status, attempts, started, summary=summarize(result))
            return result

    def attach_verification(self, tool: ToolName, verification: Verification) -> None:
        """Store the read-back on the most recent successful call of ``tool`` in this turn."""
        calls = self._recorder.tool_calls
        for index in range(len(calls) - 1, -1, -1):
            if calls[index].tool is tool and calls[index].status is ToolCallStatus.OK:
                calls[index] = calls[index].evolve(verification=verification)
                return

    # --- typed calls ----------------------------------------------------------------------------------------

    async def list_recent_transactions(self, query: TransactionQuery) -> Sequence[Transaction]:
        inner = self._inner
        return await self.run(
            ToolName.LIST_RECENT_TRANSACTIONS,
            lambda: inner.list_recent_transactions(query),
            arguments={"statuses": query.statuses, "types": query.types, "limit": query.limit},
            summarize=lambda found: f"count_{min(len(found), 999)}",
        )

    async def get_transaction(self, transaction_id: TransactionId) -> Transaction | None:
        inner = self._inner
        return await self.run(
            ToolName.GET_TRANSACTION,
            lambda: inner.get_transaction(transaction_id),
            arguments={"transaction_id": transaction_id},
        )

    async def get_product_status(self, product_id: ProductId) -> ProductStatusView | None:
        inner = self._inner
        return await self.run(
            ToolName.GET_PRODUCT_STATUS,
            lambda: inner.get_product_status(product_id),
            arguments={"product_id": product_id},
            summarize=lambda view: view.status.value if view is not None else None,
        )

    async def list_my_cards(self) -> Sequence[CardStatusView]:
        inner = self._inner
        return await self.run(
            ToolName.LIST_MY_CARDS, inner.list_my_cards, summarize=lambda found: f"count_{min(len(found), 999)}"
        )

    async def list_my_cases(self) -> Sequence[DisputeCase]:
        inner = self._inner
        return await self.run(
            ToolName.LIST_MY_CASES, inner.list_my_cases, summarize=lambda found: f"count_{min(len(found), 999)}"
        )

    async def get_case_status(self, case_id: CaseId) -> DisputeCase | None:
        inner = self._inner
        return await self.run(
            ToolName.GET_CASE_STATUS,
            lambda: inner.get_case_status(case_id),
            arguments={"case_id": case_id},
            summarize=lambda case: case.status.value if case is not None else None,
        )

    async def create_dispute_case(self, request: CreateDisputeArguments, key: IdempotencyKey) -> DisputeCase:
        inner = self._inner
        return await self.run(
            ToolName.CREATE_DISPUTE_CASE,
            lambda: inner.create_dispute_case(request, key),
            arguments={"transaction_id": request.transaction_id, "reason": request.reason},
            idempotency_key=key,
            summarize=lambda case: case.status.value,
        )

    async def block_card(self, product_id: ProductId, key: IdempotencyKey, reason: CardBlockReason | None) -> Product:
        inner = self._inner
        return await self.run(
            ToolName.BLOCK_CARD,
            lambda: inner.block_card(product_id, key, reason),
            arguments={"product_id": product_id, "reason": reason},
            idempotency_key=key,
            summarize=lambda product: product.status.value,
        )

    # --- account and credit reads, the intake write, and the engine-only profile read ------------------------

    async def list_my_balances(self) -> Sequence[BalanceView]:
        inner = self._inner
        return await self.run(
            ToolName.LIST_MY_BALANCES, inner.list_my_balances, summarize=lambda found: f"count_{min(len(found), 999)}"
        )

    async def get_payment_status(self, filters: PaymentFilter) -> Sequence[PaymentStatusView]:
        inner = self._inner
        return await self.run(
            ToolName.GET_PAYMENT_STATUS,
            lambda: inner.get_payment_status(filters),
            arguments={"statuses": filters.statuses, "limit": filters.limit},
            summarize=lambda found: f"count_{min(len(found), 999)}",
        )

    async def get_statement_summary(self, product_id: ProductId, period: DateRange) -> StatementSummary | None:
        inner = self._inner
        days = (period.end - period.start).days + 1
        return await self.run(
            ToolName.GET_STATEMENT_SUMMARY,
            lambda: inner.get_statement_summary(product_id, period),
            arguments={"product_id": product_id, "period_days": days},
            summarize=lambda summary: f"count_{min(summary.transaction_count, 999)}" if summary else None,
        )

    async def list_credit_products(self) -> Sequence[CreditProduct]:
        inner = self._inner
        return await self.run(
            ToolName.LIST_CREDIT_PRODUCTS,
            inner.list_credit_products,
            summarize=lambda found: f"count_{min(len(found), 999)}",
        )

    async def get_credit_product(self, code: CreditProductCode) -> CreditProduct | None:
        inner = self._inner
        return await self.run(
            ToolName.GET_CREDIT_PRODUCT, lambda: inner.get_credit_product(code), arguments={"product_code": code}
        )

    async def get_credit_application_status(self, application_id: ApplicationId) -> CreditApplicationIntake | None:
        inner = self._inner
        return await self.run(
            ToolName.GET_CREDIT_APPLICATION_STATUS,
            lambda: inner.get_credit_application_status(application_id),
            arguments={"application_id": application_id},
            summarize=lambda intake: intake.status.value if intake is not None else None,
        )

    async def list_my_credit_applications(self) -> Sequence[CreditApplicationIntake]:
        inner = self._inner
        return await self.run(
            ToolName.LIST_MY_CREDIT_APPLICATIONS,
            inner.list_my_credit_applications,
            summarize=lambda found: f"count_{min(len(found), 999)}",
        )

    async def submit_credit_application(
        self, request: SubmitCreditApplicationArguments, key: IdempotencyKey
    ) -> CreditApplicationIntake:
        inner = self._inner
        return await self.run(
            ToolName.SUBMIT_CREDIT_APPLICATION,
            lambda: inner.submit_credit_application(request, key),
            arguments={"product_code": request.product_code, "requested_term_months": request.requested_term_months},
            idempotency_key=key,
            summarize=lambda intake: intake.status.value,
        )

    async def engine_credit_profile(self, reader: "CreditProfileSource") -> CreditProfile | None:
        """The engine's own read of the credit profile. The tool is on no state allowlist; the call is recorded
        with no arguments and no values (the summary says only whether a profile exists)."""
        with self.engine_check(frozenset({ToolName.GET_MY_CREDIT_PROFILE})):
            return await self.run(
                ToolName.GET_MY_CREDIT_PROFILE,
                reader.get_my_credit_profile,
                summarize=lambda profile: "found" if profile is not None else None,
            )


class CreditProfileSource(Protocol):
    """``EngineOnlyTools`` satisfies it: the credit profile read that no state allowlist may reach."""

    async def get_my_credit_profile(self) -> CreditProfile | None: ...
