from decimal import Decimal

import pytest
from pydantic import ValidationError

from bank_agent.domain.actions import ToolName
from bank_agent.domain.execution_record import (
    ExecutionRecord,
    LlmCallRecord,
    LlmCallStatus,
    ToolCallRecord,
    ToolCallStatus,
)
from bank_agent.domain.intelligence import PromptRef, TokenUsage
from bank_agent.domain.workflow import Outcome
from bank_agent_builders import execution_record


def _llm_call(tokens_in: int, tokens_out: int, cost: str) -> LlmCallRecord:
    return LlmCallRecord(
        prompt=PromptRef.model_validate("extract_dispute_slots@1"),
        model_id="fake/scripted",
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        cost_usd=Decimal(cost),
        latency_ms=40,
        status=LlmCallStatus.OK,
    )


def test_totals_must_equal_the_sum_over_llm_calls() -> None:
    calls = [_llm_call(100, 20, "0.0010"), _llm_call(50, 10, "0.0005")]
    record = execution_record(
        llm_calls=calls, token_usage=TokenUsage(input_tokens=150, output_tokens=30), cost_usd=Decimal("0.0015")
    )
    assert record.cost_usd == Decimal("0.0015")
    with pytest.raises(ValidationError, match="token_usage"):
        execution_record(llm_calls=calls, cost_usd=Decimal("0.0015"))
    with pytest.raises(ValidationError, match="cost_usd"):
        execution_record(llm_calls=calls, token_usage=TokenUsage(input_tokens=150, output_tokens=30))


def test_model_call_id_is_recorded_only_under_the_new_contract_version() -> None:
    call = _llm_call(100, 20, "0.0010").evolve(model_call_id="1234567890abcdef")
    record = execution_record(
        llm_calls=[call],
        token_usage=TokenUsage(input_tokens=100, output_tokens=20),
        cost_usd=Decimal("0.0010"),
    )
    assert record.llm_calls[0].model_call_id == "1234567890abcdef"
    with pytest.raises(ValidationError, match=r"model_call_id was added in 1\.5\.0"):
        execution_record(
            schema_version="1.4.0",
            llm_calls=[call],
            token_usage=TokenUsage(input_tokens=100, output_tokens=20),
            cost_usd=Decimal("0.0010"),
        )


def test_tool_calls_are_numbered_in_order() -> None:
    call = ToolCallRecord(sequence=2, tool=ToolName.GET_TRANSACTION, status=ToolCallStatus.OK, latency_ms=3)
    with pytest.raises(ValidationError):
        execution_record(tool_calls=[call])
    assert execution_record(tool_calls=[call.evolve(sequence=1)]).tool_calls[0].tool is ToolName.GET_TRANSACTION


def test_an_escalated_turn_references_its_handoff() -> None:
    with pytest.raises(ValidationError):
        execution_record(outcome=Outcome.ESCALATED)
    assert execution_record(outcome=Outcome.ESCALATED, handoff_ref="ho-000001").handoff_ref == "ho-000001"


def test_no_stage_is_longer_than_the_turn() -> None:
    with pytest.raises(ValidationError):
        execution_record(latency={"total_ms": 10, "stages": {"llm": 11}})


def test_round_trips_through_json() -> None:
    record = execution_record()
    assert ExecutionRecord.model_validate_json(record.model_dump_json()) == record
