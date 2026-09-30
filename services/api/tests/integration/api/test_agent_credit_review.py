"""Agents take credit application intakes into human review and close them, over HTTP, audited, never a decision."""

from bank_agent.domain.access import AccessContext, Role
from bank_agent.domain.credit import CreditApplicationIntake
from bank_agent.domain.identifiers import ApplicationId, CreditProductCode, CustomerId, IdempotencyKey
from bank_agent.domain.money import Currency, Money
from bank_agent.ports.audit import AuditQuery
from bank_agent_api import EVALUATOR_ID, ApiBackend, ApiClient, ApiHarness
from bank_agent_builders import T0
from bank_agent_scenarios import MX

APPLICATION = "app-review-0001"


async def _intake(harness: ApiHarness) -> None:
    intake = CreditApplicationIntake.submit(
        application_id=ApplicationId(APPLICATION),
        customer_id=CustomerId(MX),
        product_code=CreditProductCode("MX-PL-STANDARD"),
        requested_amount=Money.of("50000.00", Currency.MXN),
        requested_term_months=24,
        purpose="general_purpose",
        idempotency_key=IdempotencyKey("idem-key-review-000001"),
        created_at=T0,
    )
    async with harness.container.persistence.uow_factory(AccessContext.for_customer(CustomerId(MX))) as uow:
        await uow.credit_applications.create(intake)
        await uow.commit()


async def test_an_agent_reviews_then_closes_an_intake_and_both_moves_are_audited(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    await _intake(harness)
    path = f"/v1/agent/credit-applications/{APPLICATION}"
    async with ApiClient(harness.app) as agent:
        await agent.login("persona-agent")
        read = await agent.get(path)
        early_close = await agent.post(f"{path}/close", {"expected_version": 0})
        reviewing = await agent.post(f"{path}/review", {"expected_version": 0})
        stale = await agent.post(f"{path}/close", {"expected_version": 0})
        closed = await agent.post(f"{path}/close", {"expected_version": 1})
        after = await agent.get(path)
        missing = await agent.post("/v1/agent/credit-applications/app-none-1/review", {"expected_version": 0})
    assert (read.json()["status"], read.json()["version"]) == ("submitted", 0)
    assert early_close.status_code == 409
    assert early_close.json()["type"].endswith("/invalid-state-transition")
    assert (reviewing.json()["status"], reviewing.json()["version"]) == ("under_human_review", 1)
    assert stale.status_code == 409
    assert stale.json()["type"].endswith("/conflict")
    assert (closed.json()["status"], closed.json()["version"]) == ("closed", 2)
    assert [change["reason_code"] for change in closed.json()["status_history"]] == [
        "credit_review_started",
        "credit_review_closed",
    ]
    assert after.status_code == 404  # closed without a handoff: no longer a review item
    assert missing.status_code == 404
    evaluator = AccessContext.for_staff(Role.EVALUATOR, EVALUATOR_ID)  # type: ignore[arg-type]
    async with harness.container.persistence.uow_factory(evaluator) as uow:
        events = [
            event
            for event in await uow.audit.list(AuditQuery(limit=500))
            if event.target is not None and event.target.key == APPLICATION
        ]
    assert sorted(event.action for event in events) == ["credit_review_closed", "credit_review_started"]
    assert all(event.actor_role is Role.AGENT for event in events)


async def test_customers_cannot_review_intakes_and_moves_need_a_csrf_token(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    await _intake(harness)
    path = f"/v1/agent/credit-applications/{APPLICATION}/review"
    async with ApiClient(harness.app) as customer, ApiClient(harness.app) as agent:
        await customer.login("persona-mx")
        refused = await customer.post(path, {"expected_version": 0})
        await agent.login("persona-agent")
        forged = await agent.post(path, {"expected_version": 0}, csrf=False)
        invalid = await agent.post(path, {"expected_version": -1})
    assert refused.status_code == 403
    assert forged.status_code == 403
    assert invalid.status_code == 422
