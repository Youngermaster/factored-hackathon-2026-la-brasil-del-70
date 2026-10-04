"""Contract version 1.3.0: the ``list_my_credit_applications`` tool name, with no field change."""

import json
from pathlib import Path
from typing import Any

import jsonschema

from bank_agent.domain.actions import WRITE_TOOLS, ToolName
from bank_agent.domain.decision import Decision
from bank_agent.domain.execution_record import ExecutionRecord, ToolCallRecord, ToolCallStatus
from bank_agent.domain.handoff import Handoff
from bank_agent_builders import execution_record

SCHEMAS = Path(__file__).resolve().parents[5] / "contracts" / "schemas"


def _schema(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((SCHEMAS / f"{name}.v1.json").read_text(encoding="utf-8"))
    return loaded


def test_every_output_contract_defaults_to_the_shared_release() -> None:
    for model in (Handoff, ExecutionRecord, Decision):
        assert model.model_fields["schema_version"].default == "1.5.0"
    assert execution_record().schema_version == "1.5.0"


def test_the_credit_application_listing_tool_is_a_read_that_fits_the_schemas() -> None:
    assert ToolName.LIST_MY_CREDIT_APPLICATIONS not in WRITE_TOOLS
    call = ToolCallRecord(sequence=1, tool=ToolName.LIST_MY_CREDIT_APPLICATIONS, status=ToolCallStatus.OK, latency_ms=2)
    document = execution_record(tool_calls=(call,)).model_dump(mode="json")
    assert list(jsonschema.Draft202012Validator(_schema("execution_record")).iter_errors(document)) == []
    assert "list_my_credit_applications" in _schema("scenario")["$defs"]["ToolName"]["enum"]


def test_no_field_is_added_in_1_3() -> None:
    for name in ("handoff", "execution_record"):
        properties = _schema(name)["properties"].values()
        assert not [value for value in properties if value.get("x-added-in") == "1.3.0"]
