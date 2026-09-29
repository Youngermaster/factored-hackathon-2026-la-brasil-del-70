"""Contract version 1.3.0: the Tuesday MVP model decision, correlation ids, assistant profile, simulated agent."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from bank_agent.domain.actions import WRITE_TOOLS, ToolName
from bank_agent.domain.assistant_profile import DEFAULT_ASSISTANT_NAME, DEFAULT_AVATAR, AssistantProfile, AvatarId
from bank_agent.domain.conversation import AssistantResponse, EscalationNotice, SimulatedAgentReply
from bank_agent.domain.execution_record import (
    ExecutionRecord,
    LlmCallRecord,
    LlmCallStatus,
    OutputSchemaRef,
    ToolCallRecord,
    ToolCallStatus,
)
from bank_agent.domain.identifiers import CustomerId, HandoffId, ModelCallId, ToolCallId
from bank_agent.domain.intelligence import PromptRef
from bank_agent.domain.llm_outputs import OUTPUT_MODELS, DecisionIntent, ModelDecision
from bank_agent.domain.locale import Language
from bank_agent.domain.workflow import Intent
from bank_agent_builders import execution_record

SCHEMAS = Path(__file__).resolve().parents[5] / "contracts" / "schemas"
T0 = datetime(2026, 6, 17, 15, 0, tzinfo=UTC)
SCHEMA_REF = OutputSchemaRef(name="ModelDecision", version="1.3.0", sha256="a" * 64)


def _schema(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((SCHEMAS / f"{name}.v1.json").read_text(encoding="utf-8"))
    return loaded


def _errors(name: str, document: Any) -> list[str]:
    return [error.message for error in jsonschema.Draft202012Validator(_schema(name)).iter_errors(document)]


def _decision(**overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "intent": "balance_inquiry",
        "confidence": 0.9,
        "account": {"product_hint": None, "statement_period_expression": None, "payment": None},
        "assistant_name": None,
    }
    return document | overrides


def _llm_call(**overrides: Any) -> LlmCallRecord:
    fields: dict[str, Any] = {
        "prompt": PromptRef.model_validate("decide_intent@1"),
        "model_id": "provider/model-a",
        "input_tokens": 10,
        "output_tokens": 5,
        "cost_usd": Decimal(0),
        "latency_ms": 120,
        "status": LlmCallStatus.OK,
    }
    return LlmCallRecord(**(fields | overrides))


def test_decision_labels_are_every_intent_plus_the_two_profile_requests() -> None:
    assert {label.value for label in DecisionIntent} == {intent.value for intent in Intent} | {
        "change_assistant_name",
        "change_assistant_avatar",
    }
    assert DecisionIntent.BALANCE_INQUIRY.intent is Intent.BALANCE_INQUIRY
    assert DecisionIntent.CHANGE_ASSISTANT_AVATAR.intent is None
    assert "clarify" not in {label.value for label in DecisionIntent}
    assert "abstain" not in {label.value for label in DecisionIntent}


def test_a_decision_validates_against_the_model_and_the_published_schema() -> None:
    decision = ModelDecision.model_validate(_decision())
    assert decision.schema_version == "1.3.0"
    assert _errors("model_decision", _decision()) == []
    assert OUTPUT_MODELS["ModelDecision"] is ModelDecision


@pytest.mark.parametrize("field", ["customer_id", "conversation_id", "session_id", "product_id", "tool"])
def test_a_decision_cannot_name_a_customer_conversation_or_tool(field: str) -> None:
    document = _decision(**{field: "C000001"})
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ModelDecision.model_validate(document)
    assert _errors("model_decision", document) != []


def test_slots_must_be_stated_and_must_match_the_intent() -> None:
    with pytest.raises(ValidationError, match="assistant_name"):
        ModelDecision.model_validate({"intent": "balance_inquiry", "confidence": 0.9, "account": None})
    with pytest.raises(ValidationError, match="account slots belong to an account inquiry"):
        ModelDecision.model_validate(_decision(intent="card_block"))
    with pytest.raises(ValidationError, match="only a rename"):
        ModelDecision.model_validate(_decision(assistant_name="Sol"))
    with pytest.raises(ValidationError, match="only a rename"):
        ModelDecision.model_validate(_decision(intent="change_assistant_name", account=None))
    rename = ModelDecision.model_validate(_decision(intent="change_assistant_name", account=None, assistant_name="Sol"))
    assert rename.assistant_name == "Sol"


@pytest.mark.parametrize("name", ["María José", "João", "D'Ana", "Ana-Lu"])
def test_assistant_names_accept_spanish_and_portuguese_words(name: str) -> None:
    assert AssistantProfile(customer_id=CustomerId("C000001"), name=name).name == name


@pytest.mark.parametrize(
    "name", ["", " Luna", "Luna ", "R2D2", "https://x.test", "<b>Luna</b>", "Luna.", "a" * 41, "Luna  Sol"]
)
def test_assistant_names_reject_digits_links_markup_and_extra_spaces(name: str) -> None:
    with pytest.raises(ValidationError):
        AssistantProfile(customer_id=CustomerId("C000001"), name=name)


def test_the_default_profile_is_luna_with_the_first_avatar_and_was_never_saved() -> None:
    profile = AssistantProfile.default(CustomerId("C000001"))
    assert (profile.name, profile.avatar_id, profile.version) == (DEFAULT_ASSISTANT_NAME, DEFAULT_AVATAR, 0)
    assert profile.is_default
    assert not profile.evolve(name="Sol", updated_at=T0, version=1).is_default
    assert [avatar.value for avatar in AvatarId] == [f"avatar-0{n}" for n in range(1, 7)]


def test_the_mvp_tools_are_recorded_but_are_not_banking_writes() -> None:
    mvp = {ToolName.ESCALATE_TO_HUMAN, ToolName.CHANGE_ASSISTANT_NAME, ToolName.MOCK_ASSISTANT_IMAGE}
    assert not mvp & WRITE_TOOLS
    calls = tuple(
        ToolCallRecord(
            sequence=n, tool=tool, status=ToolCallStatus.OK, latency_ms=1, tool_call_id=ToolCallId(f"tc-{n}")
        )
        for n, tool in enumerate(sorted(mvp), start=1)
    )
    assert _errors("execution_record", execution_record(tool_calls=calls).model_dump(mode="json")) == []


def test_a_record_links_its_request_tool_calls_and_model_calls() -> None:
    record = execution_record(
        correlation_id="req-0123456789abcdef",
        tool_calls=(
            ToolCallRecord(
                sequence=1,
                tool=ToolName.LIST_MY_BALANCES,
                status=ToolCallStatus.OK,
                latency_ms=4,
                tool_call_id=ToolCallId("tc-1"),
            ),
        ),
        llm_calls=(_llm_call(model_call_id=ModelCallId("mc-1"), provider="anthropic", output_schema=SCHEMA_REF),),
        token_usage={"input_tokens": 10, "output_tokens": 5},
    )
    assert record.schema_version == "1.3.0"
    assert ExecutionRecord.model_validate_json(record.model_dump_json()) == record
    assert _errors("execution_record", record.model_dump(mode="json")) == []


def test_a_1_2_record_cannot_carry_the_new_ids_at_any_level() -> None:
    with pytest.raises(ValidationError, match=r"added in 1\.3\.0"):
        execution_record(schema_version="1.2.0", correlation_id="req-0123456789abcdef")
    tool_call = ToolCallRecord(
        sequence=1,
        tool=ToolName.LIST_MY_BALANCES,
        status=ToolCallStatus.OK,
        latency_ms=1,
        tool_call_id=ToolCallId("tc-1"),
    )
    with pytest.raises(ValidationError, match=r"added in 1\.3\.0"):
        execution_record(schema_version="1.2.0", tool_calls=(tool_call,))
    with pytest.raises(ValidationError, match=r"added in 1\.3\.0"):
        execution_record(
            schema_version="1.2.0",
            llm_calls=(_llm_call(provider="anthropic"),),
            token_usage={"input_tokens": 10, "output_tokens": 5},
        )


def test_call_ids_are_unique_within_a_record() -> None:
    calls = (_llm_call(model_call_id="mc-1"), _llm_call(model_call_id="mc-1"))
    with pytest.raises(ValidationError, match="unique within a record"):
        execution_record(llm_calls=calls, token_usage={"input_tokens": 20, "output_tokens": 10})


def test_the_correlation_id_uses_the_request_id_format() -> None:
    with pytest.raises(ValidationError):
        execution_record(correlation_id="short")
    with pytest.raises(ValidationError):
        execution_record(correlation_id="has spaces in it")


def test_only_the_correlation_fields_are_added_in_1_3() -> None:
    schema = _schema("execution_record")
    top = {key for key, value in schema["properties"].items() if value.get("x-added-in") == "1.3.0"}
    assert top == {"correlation_id"}
    tool = {key for key, value in schema["$defs"]["ToolCallRecord"]["properties"].items() if "x-added-in" in value}
    llm = {key for key, value in schema["$defs"]["LlmCallRecord"]["properties"].items() if "x-added-in" in value}
    assert tool == {"tool_call_id"}
    assert llm == {"model_call_id", "provider", "output_schema"}
    assert "tool_call_id" not in schema["$defs"]["ToolCallRecord"].get("required", [])


def test_a_simulated_agent_is_always_labeled_and_joins_only_after_a_handoff() -> None:
    reply = SimulatedAgentReply(agent_display_name="Agente de demostracion", text="Hola.", joined_at=T0)
    assert reply.simulated is True
    with pytest.raises(ValidationError):
        SimulatedAgentReply.model_validate(reply.model_dump() | {"simulated": False})
    with pytest.raises(ValidationError, match="only a conversation that was handed off"):
        AssistantResponse(language=Language.ES, text="Hola.", simulated_agent=reply)
    notice = EscalationNotice(handoff_id=HandoffId("ho-1"), expected_response_by=T0 + timedelta(days=1))
    response = AssistantResponse(language=Language.ES, text="Hola.", escalation=notice, simulated_agent=reply)
    assert response.simulated_agent == reply
