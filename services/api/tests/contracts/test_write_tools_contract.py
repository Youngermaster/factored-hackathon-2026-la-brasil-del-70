"""Write tools over every write backend: idempotency, step-up, verification, audit, and failure injection."""

from datetime import timedelta

import pytest

from bank_agent.application.tools.banking import BankingTools
from bank_agent.application.tools.failure_injection import ToolFailureInjector
from bank_agent.application.tools.verification import WriteVerifier
from bank_agent.domain.actions import (
    CreateDisputeArguments,
    SubmitCreditApplicationArguments,
    ToolFailureMode,
    ToolName,
)
from bank_agent.domain.cards import CardBlockReason
from bank_agent.domain.dispute import DisputeReason
from bank_agent.domain.errors import (
    ConfigurationError,
    IdempotencyConflictError,
    InvalidProductStateError,
    ProductNotFoundError,
    StepUpRequiredError,
    ToolArgumentError,
    ToolTimeoutError,
    ToolTransientError,
    TransactionNotFoundError,
)
from bank_agent.domain.identifiers import CaseId, CreditProductCode, IdempotencyKey, ProductId, TransactionId
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.product import ProductStatus
from bank_agent.ports.audit import AuditQuery
from bank_agent_contracts import EVALUATOR, WriteBackend
from bank_agent_tools import session_context, tool_dependencies, tools_for

KEY = IdempotencyKey("idem-key-tools-0001")
OTHER_KEY = IdempotencyKey("idem-key-tools-0002")
DISPUTE = CreateDisputeArguments(
    transaction_id=TransactionId("TXN-A-0007"),
    reason=DisputeReason.UNRECOGNIZED,
    disputed_amount=Money.of("999.00", Currency.MXN),
)
APPLICATION = SubmitCreditApplicationArguments(
    product_code=CreditProductCode("MX-PL-FIXTURE"),
    requested_amount=Money.of("50000.00", Currency.MXN),
    requested_term_months=24,
    purpose="general_purpose",
)


class TestWriteToolsContract:
    async def test_create_dispute_case_is_idempotent_and_verified(self, write_backend: WriteBackend) -> None:
        with pytest.raises(StepUpRequiredError):
            await tools_for(write_backend.uow_factory()).create_dispute_case(DISPUTE, KEY)
        tools = tools_for(write_backend.uow_factory(), step_up=True)
        first = await tools.create_dispute_case(DISPUTE, KEY)
        assert first.sla_due_at - first.opened_at == timedelta(days=45)
        again = await tools.create_dispute_case(DISPUTE, KEY)
        assert again.case_id == first.case_id
        with pytest.raises(IdempotencyConflictError):
            await tools.create_dispute_case(DISPUTE.evolve(reason=DisputeReason.DUPLICATE), KEY)
        with pytest.raises(TransactionNotFoundError):
            await tools.create_dispute_case(DISPUTE.evolve(transaction_id="TXN-B-0001"), OTHER_KEY)
        verifier = WriteVerifier(tool_dependencies(write_backend.uow_factory()), session_context())
        verified = await verifier.dispute_case_recorded(
            first.case_id, transaction_id=DISPUTE.transaction_id, reason=DISPUTE.reason
        )
        assert verified.verified
        assert str(verified.evidence) == f"dispute_cases:{first.case_id}"
        wrong = await verifier.dispute_case_recorded(
            first.case_id, transaction_id=DISPUTE.transaction_id, reason=DisputeReason.DUPLICATE
        )
        assert (wrong.verified, wrong.mismatch_code) == (False, "case_details_differ")

    async def test_block_card_needs_step_up_and_is_idempotent(self, write_backend: WriteBackend) -> None:
        card = ProductId("PRD-A-CARD")
        with pytest.raises(StepUpRequiredError):
            await tools_for(write_backend.uow_factory()).block_card(card, KEY)
        tools = tools_for(write_backend.uow_factory(), step_up=True)
        blocked = await tools.block_card(card, KEY, CardBlockReason.LOST)
        assert blocked.status is ProductStatus.BLOCKED
        assert (await tools.block_card(card, KEY, CardBlockReason.LOST)).status is ProductStatus.BLOCKED
        with pytest.raises(IdempotencyConflictError):
            await tools.block_card(card, KEY, CardBlockReason.STOLEN)
        with pytest.raises(ProductNotFoundError):
            await tools.block_card(ProductId("PRD-B-CARD"), OTHER_KEY)
        with pytest.raises(InvalidProductStateError):
            await tools.block_card(ProductId("PRD-A-SAVE"), OTHER_KEY)
        verifier = WriteVerifier(tool_dependencies(write_backend.uow_factory()), session_context())
        assert (await verifier.card_blocked(card)).verified
        events = await write_backend.audit_log(EVALUATOR).list(AuditQuery(action="block_card"))
        assert sorted(event.outcome.value for event in events) == [
            "denied",
            "failure",
            "failure",
            "failure",
            "success",
            "success",
        ]

    async def test_submit_credit_application_is_idempotent_and_verified(self, write_backend: WriteBackend) -> None:
        with pytest.raises(StepUpRequiredError):
            await tools_for(write_backend.uow_factory()).submit_credit_application(APPLICATION, KEY)
        tools = tools_for(write_backend.uow_factory(), step_up=True)
        intake = await tools.submit_credit_application(APPLICATION, KEY)
        assert intake.status.value == "submitted"
        assert (await tools.submit_credit_application(APPLICATION, KEY)).application_id == intake.application_id
        with pytest.raises(IdempotencyConflictError):
            await tools.submit_credit_application(APPLICATION.evolve(requested_term_months=36), KEY)
        with pytest.raises(ToolArgumentError):
            await tools.submit_credit_application(APPLICATION.evolve(product_code="CO-CC-FIXTURE"), OTHER_KEY)
        verifier = WriteVerifier(tool_dependencies(write_backend.uow_factory()), session_context())
        verified = await verifier.credit_application_submitted(
            intake.application_id,
            product_code=APPLICATION.product_code,
            requested_amount=APPLICATION.requested_amount,
            requested_term_months=APPLICATION.requested_term_months,
        )
        assert verified.verified

    async def test_verification_detects_an_injected_partial_write(self, write_backend: WriteBackend) -> None:
        banking = BankingTools(tool_dependencies(write_backend.uow_factory()))
        context = session_context(step_up=True)
        plan = {
            ToolName.CREATE_DISPUTE_CASE: ToolFailureMode.PARTIAL_WRITE,
            ToolName.BLOCK_CARD: ToolFailureMode.PARTIAL_WRITE,
            ToolName.SUBMIT_CREDIT_APPLICATION: ToolFailureMode.PARTIAL_WRITE,
        }
        injector = ToolFailureInjector(
            banking.for_session(context), banking.for_session(context, commit=False), plan, environment="test"
        )
        case = await injector.create_dispute_case(DISPUTE, KEY)
        card = await injector.block_card(ProductId("PRD-A-CARD"), KEY)
        intake = await injector.submit_credit_application(APPLICATION, KEY)
        verifier = WriteVerifier(banking.dependencies, context)
        results = (
            await verifier.dispute_case_recorded(
                case.case_id, transaction_id=DISPUTE.transaction_id, reason=DISPUTE.reason
            ),
            await verifier.card_blocked(card.product_id),
            await verifier.credit_application_submitted(
                intake.application_id,
                product_code=APPLICATION.product_code,
                requested_amount=APPLICATION.requested_amount,
                requested_term_months=APPLICATION.requested_term_months,
            ),
        )
        assert [result.mismatch_code for result in results] == [
            "case_not_found",
            "product_not_blocked",
            "application_not_found",
        ]

    async def test_injected_errors_and_the_production_refusal(self, write_backend: WriteBackend) -> None:
        banking = BankingTools(tool_dependencies(write_backend.uow_factory()))
        context = session_context()
        plan = {
            ToolName.LIST_MY_CASES: ToolFailureMode.TIMEOUT,
            ToolName.LIST_MY_BALANCES: ToolFailureMode.TRANSIENT_ERROR,
        }
        injector = ToolFailureInjector(
            banking.for_session(context), banking.for_session(context, commit=False), plan, environment="test"
        )
        with pytest.raises(ToolTimeoutError):
            await injector.list_my_cases()
        with pytest.raises(ToolTransientError):
            await injector.list_my_balances()
        assert await injector.get_case_status(CaseId("case-000001")) is not None
        with pytest.raises(ConfigurationError):
            ToolFailureInjector(
                banking.for_session(context), banking.for_session(context), plan, environment="production"
            )
        with pytest.raises(ConfigurationError):
            ToolFailureInjector(
                banking.for_session(context),
                banking.for_session(context),
                {ToolName.LIST_MY_CASES: ToolFailureMode.PARTIAL_WRITE},
                environment="test",
            )
