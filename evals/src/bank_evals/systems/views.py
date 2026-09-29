"""Normalize the engine's turn results, execution records, and store into the transcript model."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

import jsonschema

from bank_agent.adapters.persistence.memory.store import InMemoryStore
from bank_agent.domain.conversation import ActionDisplayStatus, TurnResult
from bank_agent.domain.execution_record import ExecutionRecord
from bank_evals.systems.base import EndState, LlmCallView, ToolCallView, TurnView

HANDOFF_SCHEMA = Path(__file__).resolve().parents[4] / "contracts" / "schemas" / "handoff.v1.json"


@cache
def handoff_validator() -> jsonschema.Draft202012Validator:
    schema = json.loads(HANDOFF_SCHEMA.read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema)


def schema_valid(document: dict[str, Any]) -> bool:
    return not any(True for _ in handoff_validator().iter_errors(document))


def turn_view(
    index: int, text: str, result: TurnResult, record: ExecutionRecord | None, latency_ms: int, customer_id: str
) -> TurnView:
    response = result.response
    tool_calls: list[ToolCallView] = []
    llm_calls: list[LlmCallView] = []
    if record is not None:
        tool_calls = [
            ToolCallView(
                tool=call.tool.value,
                status=call.status.value,
                arguments={key: str(value) for key, value in call.arguments.items()},
                verified=call.verification.verified if call.verification is not None else None,
                customer_id=customer_id,
            )
            for call in record.tool_calls
        ]
        llm_calls = [
            LlmCallView(
                prompt=str(call.prompt),
                model=call.model_id,
                status=call.status.value,
                input_tokens=call.input_tokens,
                output_tokens=call.output_tokens,
                cost_usd=call.cost_usd,
                latency_ms=call.latency_ms,
            )
            for call in record.llm_calls
        ]
    verified = [s.action.value for s in response.action_statuses if s.status is ActionDisplayStatus.VERIFIED]
    return TurnView(
        index=index,
        customer_text=text,
        assistant_text=response.text,
        outcome=result.outcome.value,
        state=result.state,
        workflow=result.workflow.id if result.workflow is not None else None,
        workflow_before=record.workflow_before.id if record is not None and record.workflow_before else None,
        language=response.language.value,
        template_id=response.template_id,
        latency_ms=latency_ms,
        tool_calls=tool_calls,
        llm_calls=llm_calls,
        step_up_required=response.step_up_required,
        notices=[notice.value for notice in response.notices],
        handoff_id=response.escalation.handoff_id if response.escalation is not None else None,
        verified_actions=verified,
        claimed_actions=verified,
        eligibility_outcome=response.eligibility.outcome.value if response.eligibility is not None else None,
        balances=[view.model_dump(mode="json") for view in response.balances],
        citations=[str(citation.clause) for citation in response.citations],
        safety_interventions=list(record.safety_interventions) if record is not None else [],
    )


def end_state(store: InMemoryStore, before: EndState | None) -> EndState:
    cases = [
        {"case_id": case.case_id, "transaction_id": case.transaction_id, "customer_id": case.customer_id,
         "reason": case.reason.value, "status": case.status.value}
        for case in store.cases.values()
    ]  # fmt: skip
    applications = [
        {"application_id": item.application_id, "customer_id": item.customer_id,
         "product_code": item.product_code, "status": item.status.value}
        for item in store.credit_applications.values()
    ]  # fmt: skip
    handoffs = []
    for stored in store.handoffs.values():
        document = stored.handoff.model_dump(mode="json")
        handoffs.append({"document": document, "schema_valid": schema_valid(document)})
    statuses = {product_id: product.status.value for product_id, product in store.products.items()}
    state = EndState(product_statuses=statuses, cases=cases, applications=applications, handoffs=handoffs)
    if before is not None:
        new_cases = {c["case_id"] for c in cases} - {c["case_id"] for c in before.cases}
        new_apps = {a["application_id"] for a in applications} - {a["application_id"] for a in before.applications}
        changed = [p for p, s in statuses.items() if before.product_statuses.get(p) != s]
        state.writes = len(new_cases) + len(new_apps) + len(changed)
    return state
