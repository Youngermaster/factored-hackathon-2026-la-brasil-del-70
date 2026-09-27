"""Read-backs that confirm each write in a fresh unit of work, returning a ``Verification`` with evidence.

A write counts as done only when its read-back finds the expected state; the workflow reports nothing else.
"""

from bank_agent.application.tools.base import ToolDependencies
from bank_agent.application.tools.context import SessionContext
from bank_agent.domain.actions import Verification
from bank_agent.domain.credit import ApplicationStatus
from bank_agent.domain.dispute import DisputeReason
from bank_agent.domain.identifiers import ApplicationId, CaseId, ProductId, SourceRef, SourceTable, TransactionId
from bank_agent.domain.money import Money
from bank_agent.domain.product import ProductStatus


class WriteVerifier:
    def __init__(self, deps: ToolDependencies, context: SessionContext) -> None:
        self._deps = deps
        self._context = context

    def _result(self, check: str, evidence: SourceRef, mismatch: str | None) -> Verification:
        now = self._deps.clock.now()
        if mismatch is None:
            return Verification(verified=True, check=check, evidence=evidence, checked_at=now)
        return Verification(verified=False, check=check, mismatch_code=mismatch, checked_at=now)

    async def dispute_case_recorded(
        self, case_id: CaseId, *, transaction_id: TransactionId, reason: DisputeReason
    ) -> Verification:
        async with self._deps.uow_factory(self._context.access) as uow:
            case = await uow.cases.get(case_id)
        mismatch = None
        if case is None:
            mismatch = "case_not_found"
        elif case.transaction_id != transaction_id or case.reason is not reason:
            mismatch = "case_details_differ"
        elif not case.is_open:
            mismatch = "case_not_open"
        return self._result("dispute_case_recorded", SourceRef.of(SourceTable.DISPUTE_CASES, case_id), mismatch)

    async def card_blocked(self, product_id: ProductId) -> Verification:
        async with self._deps.uow_factory(self._context.access) as uow:
            product = await uow.products.get(product_id)
        mismatch = None
        if product is None:
            mismatch = "product_not_found"
        elif product.status is not ProductStatus.BLOCKED:
            mismatch = "product_not_blocked"
        return self._result("card_blocked", SourceRef.of(SourceTable.PRODUCTS, product_id), mismatch)

    async def credit_application_submitted(
        self, application_id: ApplicationId, *, product_code: str, requested_amount: Money, requested_term_months: int
    ) -> Verification:
        async with self._deps.uow_factory(self._context.access) as uow:
            intake = await uow.credit_applications.get(application_id)
        mismatch = None
        if intake is None:
            mismatch = "application_not_found"
        elif (intake.product_code, intake.requested_amount, intake.requested_term_months) != (
            product_code,
            requested_amount,
            requested_term_months,
        ):
            mismatch = "application_details_differ"
        elif intake.status is not ApplicationStatus.SUBMITTED:
            mismatch = "application_status_unexpected"
        evidence = SourceRef.of(SourceTable.CREDIT_APPLICATIONS, application_id)
        return self._result("credit_application_submitted", evidence, mismatch)
