"""Write tools: dispute intake, a protective card block, and a credit application intake.

Every write is idempotent by key and never moves money or decides credit. Card unblock and replacement have no
tool by design: the workflow hands them off.
"""

import hashlib

from bank_agent.application.tools.base import ToolCalls
from bank_agent.domain.actions import (
    ActionKind,
    ActionLedgerEntry,
    CreateDisputeArguments,
    SubmitCreditApplicationArguments,
    ToolName,
)
from bank_agent.domain.cards import CardBlockReason
from bank_agent.domain.credit import CreditApplicationIntake
from bank_agent.domain.dispute import DisputeCase
from bank_agent.domain.errors import (
    IdempotencyConflictError,
    InvalidProductStateError,
    ProductNotFoundError,
    StepUpRequiredError,
    ToolArgumentError,
    TransactionNotFoundError,
)
from bank_agent.domain.identifiers import (
    ApplicationId,
    CaseId,
    IdempotencyKey,
    IdKind,
    ProductId,
    SourceRef,
    SourceTable,
)
from bank_agent.domain.product import Product, ProductStatus
from bank_agent.ports.unit_of_work import UnitOfWork


def _block_digest(product_id: ProductId, reason: CardBlockReason | None) -> str:
    return hashlib.sha256(f"block_card|{product_id}|{reason.value if reason else ''}".encode()).hexdigest()


class WriteTools(ToolCalls):
    def _require_step_up(self, action: ActionKind) -> None:
        """Writes the policy matrix marks as step-up need a valid step-up window (CLAUDE.md section 7)."""
        if action in self._deps.settings.policy.step_up_actions and not self._context.step_up_valid:
            raise StepUpRequiredError()

    async def create_dispute_case(
        self, request: CreateDisputeArguments, idempotency_key: IdempotencyKey
    ) -> DisputeCase:
        """Open a case for one of the customer's transactions, with the SLA of the customer's country.

        Needs step-up when the policy matrix says so; the same key returns the same case.
        """
        deps, at = self._deps, self._context.at

        async def work(uow: UnitOfWork) -> DisputeCase:
            self._require_step_up(ActionKind.CREATE_DISPUTE_CASE)
            existing = await uow.cases.find_by_idempotency_key(idempotency_key)
            if existing is not None:
                same = (existing.transaction_id, existing.reason, existing.disputed_amount) == (
                    request.transaction_id,
                    request.reason,
                    request.disputed_amount,
                )
                if not same:
                    raise IdempotencyConflictError()
                return existing
            transaction = await uow.transactions.get(request.transaction_id)
            if transaction is None:
                raise TransactionNotFoundError()
            country = (await uow.customers.get_current()).country
            case = DisputeCase.open(
                case_id=CaseId(deps.ids.new(IdKind.CASE)),
                transaction=transaction,
                reason=request.reason,
                opened_at=at,
                sla_due_at=at + deps.settings.policy.dispute_sla(country),
                idempotency_key=idempotency_key,
                disputed_amount=request.disputed_amount,
            )
            return await uow.cases.add(case)

        return await self._run(
            ToolName.CREATE_DISPUTE_CASE,
            work,
            arguments={"transaction_id": request.transaction_id, "reason": request.reason},
            target=lambda case: SourceRef.of(SourceTable.DISPUTE_CASES, case.case_id),
        )

    async def block_card(
        self, product_id: ProductId, idempotency_key: IdempotencyKey, reason: CardBlockReason | None = None
    ) -> Product:
        """Block an active card. Needs a valid step-up window; the same key replays the first outcome."""
        at = self._context.at
        digest = _block_digest(product_id, reason)

        async def work(uow: UnitOfWork) -> Product:
            self._require_step_up(ActionKind.BLOCK_CARD)
            recorded = await uow.action_ledger.find(ActionKind.BLOCK_CARD, idempotency_key)
            if recorded is not None and recorded.request_digest != digest:
                raise IdempotencyConflictError()
            product = await uow.products.get(product_id)
            if product is None:
                raise ProductNotFoundError()
            if recorded is None:
                if not product.is_card:
                    raise InvalidProductStateError("only cards can be blocked")
                if product.status is not ProductStatus.BLOCKED:
                    product = await uow.products.update_status(
                        product_id, ProductStatus.BLOCKED, expected=ProductStatus.ACTIVE
                    )
                await uow.action_ledger.record(
                    ActionLedgerEntry(
                        action=ActionKind.BLOCK_CARD,
                        idempotency_key=idempotency_key,
                        target=SourceRef.of(SourceTable.PRODUCTS, product_id),
                        request_digest=digest,
                        outcome=product.status.value,
                        recorded_at=at,
                    )
                )
            return product

        return await self._run(
            ToolName.BLOCK_CARD,
            work,
            arguments={"product_id": product_id, "reason": reason},
            target=lambda product: SourceRef.of(SourceTable.PRODUCTS, product.product_id),
        )

    async def submit_credit_application(
        self, request: SubmitCreditApplicationArguments, idempotency_key: IdempotencyKey
    ) -> CreditApplicationIntake:
        """Record an intake with status ``submitted`` for human review. It never decides and never moves money.

        Needs step-up when the policy matrix says so.
        """
        deps, at = self._deps, self._context.at

        async def work(uow: UnitOfWork) -> CreditApplicationIntake:
            self._require_step_up(ActionKind.SUBMIT_CREDIT_APPLICATION)
            customer = await uow.customers.get_current()
            product = deps.catalog.get(request.product_code)
            if product is None or product.jurisdiction is not customer.country:
                raise ToolArgumentError("the credit product is not offered in the customer's jurisdiction")
            if request.requested_amount.currency is not product.currency:
                raise ToolArgumentError("the requested amount must be in the product currency")
            intake = CreditApplicationIntake.submit(
                application_id=ApplicationId(deps.ids.new(IdKind.APPLICATION)),
                customer_id=customer.customer_id,
                product_code=request.product_code,
                requested_amount=request.requested_amount,
                requested_term_months=request.requested_term_months,
                purpose=request.purpose,
                idempotency_key=idempotency_key,
                created_at=at,
                declared_monthly_income=request.declared_monthly_income,
                assessment_ref=request.assessment_ref,
                origin_conversation_id=request.origin_conversation_id,
            )
            return await uow.credit_applications.create(intake)

        return await self._run(
            ToolName.SUBMIT_CREDIT_APPLICATION,
            work,
            arguments={
                "product_code": request.product_code,
                "requested_amount": request.requested_amount,
                "requested_term_months": request.requested_term_months,
                "purpose": request.purpose,
                "declared_monthly_income": request.declared_monthly_income,
            },
            target=lambda intake: SourceRef.of(SourceTable.CREDIT_APPLICATIONS, intake.application_id),
        )
