"""The agent inbox, the customer and evaluator traces, and the published evaluation summaries over HTTP."""

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from bank_agent.domain.access import AccessContext, Role
from bank_agent.domain.credit import CreditApplicationIntake
from bank_agent.domain.eligibility import CreditReview
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.handoff import EscalationReason
from bank_agent.domain.identifiers import ApplicationId, CreditProductCode, CustomerId, HandoffId, IdempotencyKey
from bank_agent.domain.money import Currency, Money
from bank_agent.ports.audit import AuditQuery
from bank_agent_api import EVALUATOR_ID, ApiBackend, ApiClient
from bank_agent_builders import T0, eligibility_assessment, handoff_v1_1
from bank_agent_scenarios import MX, PT

RISK_VALUE_KEYS = {"probability", "interval_low", "interval_high", "band"}


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in _keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in _keys(item)}
    return set()


async def _credit_review_handoff(client: ApiClient) -> str:
    await client.login("persona-mx")
    conversation = await client.open_conversation()
    text = "Quiero saber si califico para un préstamo personal de 50 mil pesos a 24 meses"
    explained = await client.say(conversation, text)
    assert explained.json()["message"]["eligibility"]["outcome"] == "insufficient_data"
    handed = await client.say(conversation, "sí, que lo revise una persona")
    assert handed.json()["state"] == "ESCALATED", handed.text
    return str(handed.json()["message"]["escalation"]["handoff_id"])


async def test_agents_filter_read_claim_and_resolve_handoffs_and_the_moves_are_audited(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    async with ApiClient(harness.app) as customer, ApiClient(harness.app) as agent:
        handoff_id = await _credit_review_handoff(customer)
        await agent.login("persona-agent")
        credit = await agent.get("/v1/agent/handoffs", params={"workflow": "credit", "status": "open"})
        disputes = await agent.get("/v1/agent/handoffs", params={"workflow": "dispute"})
        detail = await agent.get(f"/v1/agent/handoffs/{handoff_id}")
        claimed = await agent.post(f"/v1/agent/handoffs/{handoff_id}/claim")
        resolved = await agent.post(
            f"/v1/agent/handoffs/{handoff_id}/resolve", {"outcome": "referred_to_specialist", "note": "Needs income."}
        )
        again = await agent.post(f"/v1/agent/handoffs/{handoff_id}/claim")
        missing = await agent.get("/v1/agent/handoffs/ho-none")
    assert [item["handoff_id"] for item in credit.json()["handoffs"]] == [handoff_id]
    assert disputes.json()["handoffs"] == []
    view = detail.json()
    assert view["escalation_reason"]["code"] == "credit_review_required"
    assert view["credit_review"]["risk"]["band"]
    assert "transcript" not in _keys(view)
    assert (claimed.json()["status"], resolved.json()["status"]) == ("claimed", "resolved")
    assert resolved.json()["resolution"]["outcome"] == "referred_to_specialist"
    assert again.status_code == 409
    assert missing.status_code == 404
    evaluator = AccessContext.for_staff(Role.EVALUATOR, EVALUATOR_ID)  # type: ignore[arg-type]
    async with harness.container.persistence.uow_factory(evaluator) as uow:
        actions = [event.action for event in await uow.audit.list(AuditQuery(limit=500))]
    assert {"login_verified", "conversation_created", "handoff_claimed", "handoff_resolved"} <= set(actions)


async def test_customer_traces_hide_risk_values_and_evaluator_traces_show_them(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    async with ApiClient(harness.app) as customer, ApiClient(harness.app) as evaluator:
        await customer.login("persona-pt", language="pt")
        conversation = await customer.open_conversation()
        await customer.say(conversation, "Sou elegível para um cartão de crédito com limite de 30 mil pesos?")
        mine = await customer.get(f"/v1/conversations/{conversation}/trace")
        await evaluator.login("persona-evaluator")
        staff = await evaluator.get(f"/v1/eval/conversations/{conversation}/trace")
        unknown = await evaluator.get("/v1/eval/conversations/conv-none/trace")
    (record,) = mine.json()["records"]
    assert record["risk_estimates_used"][0]["model"] == "risk_estimator:score_band@1"
    assert not RISK_VALUE_KEYS & _keys(mine.json())
    assert not {"session_ref", "trust_events_added", "risk_tier", "safety_interventions"} & set(record)
    assert record["eligibility_assessments"][0]["outcome"] == "indicatively_eligible"
    (staff_record,) = staff.json()["records"]
    assert 0 <= float(staff_record["risk_estimates"][0]["probability"]) <= 1
    assert staff_record["risk_tier"] == "low"
    assert unknown.status_code == 404


async def test_agents_read_the_credit_intakes_a_handoff_references(memory_api: ApiBackend) -> None:
    harness = memory_api.build()
    application = CreditApplicationIntake.submit(
        application_id=ApplicationId("app-api-01"),
        customer_id=CustomerId(MX),
        product_code=CreditProductCode("MX-PL-STANDARD"),
        requested_amount=Money.of("50000.00", Currency.MXN),
        requested_term_months=24,
        purpose="general_purpose",
        idempotency_key=IdempotencyKey("idem-key-api-fixture-0001"),
        created_at=T0,
    )
    review = CreditReview.from_assessment(
        eligibility_assessment(outcome="review_required", review_reasons=["borderline_risk_interval"]),
        application_ref=application.application_id,
    )
    handoff = handoff_v1_1(
        handoff_id=HandoffId("ho-api-credit-01"), customer_ref=MX, case_ref=None, actions_taken=[],
        escalation_reason=EscalationReason(code=EscalationReasonCode.CREDIT_REVIEW_REQUIRED, detail="Borderline."),
        credit_review=review,
    )  # fmt: skip
    async with harness.container.persistence.uow_factory(AccessContext.for_customer(CustomerId(MX))) as uow:
        await uow.credit_applications.create(application)
        await uow.handoffs.add(handoff)
        await uow.commit()
    async with ApiClient(harness.app) as agent:
        await agent.login("persona-agent")
        listed = await agent.get("/v1/agent/credit-applications", params={"status": "submitted"})
        detail = await agent.get("/v1/agent/credit-applications/app-api-01")
        missing = await agent.get("/v1/agent/credit-applications/app-none")
    assert [item["application_id"] for item in listed.json()["applications"]] == ["app-api-01"]
    assert (detail.json()["status"], detail.json()["synthetic_policy"]) == ("submitted", True)
    assert missing.status_code == 404


def _intake(application_id: str, customer: str, key: str, created_at: Any) -> CreditApplicationIntake:
    return CreditApplicationIntake.submit(
        application_id=ApplicationId(application_id),
        customer_id=CustomerId(customer),
        product_code=CreditProductCode("MX-PL-STANDARD"),
        requested_amount=Money.of("50000.00", Currency.MXN),
        requested_term_months=24,
        purpose="general_purpose",
        idempotency_key=IdempotencyKey(key),
        created_at=created_at,
    )


async def test_agents_list_every_reviewable_intake_without_a_handoff(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    older = _intake("app-api-11", MX, "idem-key-api-fixture-0011", T0 - timedelta(days=1))
    newer = _intake("app-api-12", MX, "idem-key-api-fixture-0012", T0)
    mx, pt = AccessContext.for_customer(CustomerId(MX)), AccessContext.for_customer(CustomerId(PT))
    async with harness.container.persistence.uow_factory(mx) as uow:
        await uow.credit_applications.create(older)
        await uow.credit_applications.create(newer)
        await uow.commit()
    async with ApiClient(harness.app) as agent, ApiClient(harness.app) as customer:
        await agent.login("persona-agent")
        listed = await agent.get("/v1/agent/credit-applications")
        detail = await agent.get("/v1/agent/credit-applications/app-api-11")
        await customer.login("persona-pt", language="pt")
        refused = await customer.get("/v1/agent/credit-applications")
    assert [item["application_id"] for item in listed.json()["applications"]] == ["app-api-12", "app-api-11"]
    assert detail.json()["status"] == "submitted"
    assert refused.status_code == 403
    async with harness.container.persistence.uow_factory(pt) as uow:
        assert await uow.credit_applications.list_mine() == []
        assert await uow.credit_applications.get(ApplicationId("app-api-11")) is None
    async with harness.container.persistence.uow_factory(mx) as uow:
        assert [item.application_id for item in await uow.credit_applications.list_mine()] == [
            "app-api-12",
            "app-api-11",
        ]


def _summary(run_id: str, generated_at: str) -> dict[str, Any]:
    counts = {"count": 1, "denominator": 2}
    metrics = {"cases": 2, "safe_automated_resolution": counts, "containment": counts, "escalation_missed": counts,
               "escalation_unnecessary": counts, "unsafe_outcomes": {"count": 0, "denominator": 2}}  # fmt: skip
    return {
        "run_id": run_id, "system": "proposed", "generated_at": generated_at, "git_sha": "abc1234",
        "dataset_version": "scenarios-v1", "workflows": [{"workflow": "dispute", **metrics}], "aggregate": metrics,
    }  # fmt: skip


async def test_evaluation_summaries_are_for_evaluators_unless_published_publicly(
    api_backend: ApiBackend, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "old.json").write_text(json.dumps(_summary("run-1", "2026-09-01T00:00:00Z")), encoding="utf-8")
    (tmp_path / "new.json").write_text(json.dumps(_summary("run-2", "2026-09-02T00:00:00Z")), encoding="utf-8")
    monkeypatch.setenv("EVAL_SUMMARIES_DIR", str(tmp_path))
    private = api_backend.build()
    async with ApiClient(private.app) as anonymous, ApiClient(private.app) as evaluator:
        refused = await anonymous.get("/v1/eval/summaries")
        await evaluator.login("persona-evaluator")
        listed = await evaluator.get("/v1/eval/summaries")
    assert refused.status_code == 401
    assert [item["run_id"] for item in listed.json()["summaries"]] == ["run-2", "run-1"]
    assert listed.json()["summaries"][0]["measurement"] == "offline"
    monkeypatch.setenv("EVAL_SUMMARIES_PUBLIC", "true")
    public = api_backend.build()
    async with ApiClient(public.app) as anonymous:
        assert (await anonymous.get("/v1/eval/summaries")).status_code == 200
    (tmp_path / "broken.json").write_text("{}", encoding="utf-8")
    async with ApiClient(public.app) as anonymous:
        broken = await anonymous.get("/v1/eval/summaries")
    assert broken.status_code == 500
    assert "broken" not in broken.text
