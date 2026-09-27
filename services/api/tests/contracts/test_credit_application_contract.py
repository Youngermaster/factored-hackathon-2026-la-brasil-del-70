from datetime import timedelta
from typing import Any

import pytest

from bank_agent.domain.credit import ApplicationStatus, CreditApplicationIntake
from bank_agent.domain.eligibility import CreditReview
from bank_agent.domain.errors import (
    AccessContextError,
    ConcurrencyConflictError,
    CreditApplicationNotFoundError,
    DuplicateEntityError,
    IdempotencyConflictError,
    InvalidApplicationTransitionError,
)
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.handoff import EscalationReason
from bank_agent.domain.identifiers import ApplicationId, CreditProductCode, CustomerId, HandoffId, IdempotencyKey
from bank_agent.domain.money import Currency, Money
from bank_agent_builders import CUSTOMER_A, CUSTOMER_B, T0, eligibility_assessment, handoff_v1_1
from bank_agent_contracts import AGENT, CONTEXT_A, CONTEXT_B, EVALUATOR, WriteBackend

EXISTING = ApplicationId("app-000001")


def _intake(application_id: str = "app-000002", key: str = "idem-key-fixture-app-0100", **overrides: Any) -> Any:
    fields: dict[str, Any] = {
        "application_id": ApplicationId(application_id),
        "customer_id": CustomerId(CUSTOMER_A),
        "product_code": CreditProductCode("MX-CC-FIXTURE"),
        "requested_amount": Money.of("30000.00", Currency.MXN),
        "requested_term_months": 12,
        "purpose": "general_purpose",
        "idempotency_key": IdempotencyKey(key),
        "created_at": T0,
    }
    return CreditApplicationIntake.submit(**{**fields, **overrides})


class TestCreditApplicationRepositoryContract:
    async def test_creates_and_reads_back_an_application(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            stored = await uow.credit_applications.create(_intake())
            await uow.commit()
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            assert await uow.credit_applications.get(stored.application_id) == stored
            listed = await uow.credit_applications.list_mine()
        assert [item.application_id for item in listed] == ["app-000002", "app-000001"]

    async def test_creating_the_same_request_again_returns_the_stored_intake(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            first = await uow.credit_applications.create(_intake())
            replay = await uow.credit_applications.create(_intake("app-000003", created_at=T0 + timedelta(minutes=1)))
            await uow.commit()
        assert replay == first
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            assert len(await uow.credit_applications.list_mine()) == 2

    async def test_reusing_a_key_or_an_id_conflicts(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            await uow.credit_applications.create(_intake())
            with pytest.raises(IdempotencyConflictError):
                await uow.credit_applications.create(
                    _intake("app-000003", requested_amount=Money.of("1.00", Currency.MXN))
                )
            with pytest.raises(DuplicateEntityError):
                await uow.credit_applications.create(_intake("app-000002", key="idem-key-fixture-app-0200"))

    async def test_cannot_create_an_application_for_another_customer(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            with pytest.raises(AccessContextError):
                await uow.credit_applications.create(_intake(customer_id=CustomerId(CUSTOMER_B)))

    async def test_another_customers_application_behaves_like_a_missing_one(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_B) as uow:
            assert await uow.credit_applications.get(EXISTING) is None
            assert await uow.credit_applications.list_mine() == []
            with pytest.raises(CreditApplicationNotFoundError):
                await uow.credit_applications.transition(
                    EXISTING, ApplicationStatus.WITHDRAWN, expected_version=0, at=T0, reason_code="customer_request"
                )

    async def test_filters_by_status_and_limits(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            await uow.credit_applications.create(_intake())
            submitted = await uow.credit_applications.list_mine(frozenset({ApplicationStatus.SUBMITTED}), limit=1)
            withdrawn = await uow.credit_applications.list_mine(frozenset({ApplicationStatus.WITHDRAWN}))
        assert [item.application_id for item in submitted] == ["app-000002"]
        assert withdrawn == []

    async def test_a_customer_withdraws_with_an_optimistic_version(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            moved = await uow.credit_applications.transition(
                EXISTING, ApplicationStatus.WITHDRAWN, expected_version=0, at=T0, reason_code="customer_request"
            )
            await uow.commit()
        assert (moved.status, moved.version) == (ApplicationStatus.WITHDRAWN, 1)
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            stored = await uow.credit_applications.get(EXISTING)
            assert stored == moved
            with pytest.raises(ConcurrencyConflictError):
                await uow.credit_applications.transition(
                    EXISTING, ApplicationStatus.WITHDRAWN, expected_version=0, at=T0, reason_code="again"
                )
            with pytest.raises(InvalidApplicationTransitionError):
                await uow.credit_applications.transition(
                    EXISTING, ApplicationStatus.WITHDRAWN, expected_version=1, at=T0, reason_code="again"
                )

    async def test_a_customer_cannot_review_or_close_an_application(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            for status in (ApplicationStatus.UNDER_HUMAN_REVIEW, ApplicationStatus.CLOSED):
                with pytest.raises(AccessContextError):
                    await uow.credit_applications.transition(
                        EXISTING, status, expected_version=0, at=T0, reason_code="self_review"
                    )

    async def test_an_uncommitted_intake_is_not_visible(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            await uow.credit_applications.create(_intake())
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            assert await uow.credit_applications.get(ApplicationId("app-000002")) is None

    async def test_an_agent_reads_only_applications_a_handoff_references(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(AGENT) as uow:
            assert await uow.credit_applications.get(EXISTING) is None
        review = CreditReview.from_assessment(
            eligibility_assessment(outcome="review_required", review_reasons=["borderline_risk_interval"]),
            application_ref=EXISTING,
        )
        document = handoff_v1_1(
            handoff_id=HandoffId("ho-credit-01"),
            case_ref=None,
            actions_taken=[],
            escalation_reason=EscalationReason(
                code=EscalationReasonCode.CREDIT_REVIEW_REQUIRED, detail="Borderline indicative result."
            ),
            credit_review=review,
        )
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            await uow.handoffs.add(document)
            await uow.commit()
        async with write_backend.uow_factory()(AGENT) as uow:
            application = await uow.credit_applications.get(EXISTING)
            assert application is not None
            assert application.customer_id == CUSTOMER_A
            with pytest.raises(AccessContextError):
                await uow.credit_applications.list_mine()

    async def test_evaluators_are_refused(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(EVALUATOR) as uow:
            with pytest.raises(AccessContextError):
                await uow.credit_applications.get(EXISTING)
