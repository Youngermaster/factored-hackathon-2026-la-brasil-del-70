"""The ``AddedIn`` marker keeps stored documents valid when a contract gains a minor version."""

import json
from pathlib import Path
from typing import Annotated, Any

import jsonschema
import pytest
from pydantic import ValidationError, model_validator

from bank_agent.domain.base import AddedIn, DomainModel, added_fields, check_added_fields, parse_schema_version
from bank_agent.domain.handoff import Handoff
from bank_agent.domain.workflow import WorkflowRef

GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "contracts" / "v1.0.0" / "handoff.json"


def _golden_handoff() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(GOLDEN.read_text(encoding="utf-8"))
    return document


class _Note(DomainModel):
    code: str
    level: int = 1


class _Document(DomainModel):
    schema_version: str = "1.1.0"
    title: str
    count: int = 0
    note: Annotated[_Note | None, AddedIn("1.1.0")] = None
    tags: Annotated[tuple[str, ...], AddedIn("1.2.0")] = ()

    @model_validator(mode="after")
    def _gate(self) -> "_Document":
        check_added_fields(self, self.schema_version)
        return self


def test_parses_semantic_versions() -> None:
    assert parse_schema_version("1.10.2") == (1, 10, 2)
    assert parse_schema_version("1.2.0") > parse_schema_version("1.1.9")
    with pytest.raises(ValueError, match=r"MAJOR\.MINOR\.PATCH"):
        parse_schema_version("1.1")


def test_the_marker_rejects_a_malformed_version() -> None:
    with pytest.raises(ValueError, match="MAJOR"):
        AddedIn("v2")


def test_finds_marked_fields() -> None:
    assert {name: marker.version for name, marker in added_fields(_Document).items()} == {
        "note": "1.1.0",
        "tags": "1.2.0",
    }


def test_marked_fields_are_optional_and_annotated_in_serialization_schemas() -> None:
    schema = _Document.model_json_schema(mode="serialization")
    assert schema["required"] == ["schema_version", "title", "count"]
    assert schema["properties"]["note"]["x-added-in"] == "1.1.0"
    assert schema["$defs"]["_Note"]["required"] == ["code", "level"]


def test_validation_schemas_are_unaffected() -> None:
    assert _Document.model_json_schema(mode="validation")["required"] == ["title"]


def test_a_model_whose_every_required_field_is_marked_has_no_required_list() -> None:
    class _AllNew(DomainModel):
        extra: Annotated[int, AddedIn("1.1.0")] = 0

    assert "required" not in _AllNew.model_json_schema(mode="serialization")


def test_the_version_gate_constrains_only_marked_fields() -> None:
    assert _Document(schema_version="1.0.0", title="t", count=3).note is None
    with pytest.raises(ValidationError, match=r"note was added in 1\.1\.0"):
        _Document(schema_version="1.0.0", title="t", note=_Note(code="x"))
    assert _Document(schema_version="1.1.0", title="t", note=_Note(code="x")).note is not None
    with pytest.raises(ValidationError, match=r"tags was added in 1\.2\.0"):
        _Document(schema_version="1.1.5", title="t", tags=("a",))
    assert _Document(schema_version="1.2.0", title="t", tags=("a",)).tags == ("a",)


def test_negative_control_an_unmarked_new_field_breaks_stored_documents() -> None:
    """Without the marker, a new optional field becomes required and the stored 1.0.0 handoff fails."""

    class _Unmarked(Handoff):
        workflow: WorkflowRef | None = None

    class _Marked(Handoff):
        workflow: Annotated[WorkflowRef | None, AddedIn("1.1.0")] = None

    document = _golden_handoff()
    unmarked = jsonschema.Draft202012Validator(_Unmarked.model_json_schema(mode="serialization"))
    assert [error.message for error in unmarked.iter_errors(document)] == ["'workflow' is a required property"]
    marked = jsonschema.Draft202012Validator(_Marked.model_json_schema(mode="serialization"))
    assert list(marked.iter_errors(document)) == []
    assert _Marked.model_validate(document).schema_version == "1.0.0"
