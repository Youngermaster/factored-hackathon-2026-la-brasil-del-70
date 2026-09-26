"""Documents stored under version 1.0.0 of the output contracts stay valid under every later 1.x version.

The golden documents in ``tests/fixtures/contracts/v1.0.0`` were produced by the phase 02 builders before any
minor-version field existed. They must validate against the current models, keep their ``schema_version``, and
validate against the committed schemas in ``contracts/schemas``.
"""

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import BaseModel

from bank_agent.domain.decision import Decision
from bank_agent.domain.execution_record import ExecutionRecord
from bank_agent.domain.handoff import Handoff

TESTS = Path(__file__).resolve().parents[2]
REPOSITORY = TESTS.parents[2]
GOLDEN = TESTS / "fixtures" / "contracts" / "v1.0.0"
SCHEMAS = REPOSITORY / "contracts" / "schemas"

CASES = [
    pytest.param("handoff", Handoff, id="handoff"),
    pytest.param("execution_record", ExecutionRecord, id="execution_record"),
    pytest.param("decision", Decision, id="decision"),
]


def golden(name: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((GOLDEN / f"{name}.json").read_text(encoding="utf-8"))
    return document


def schema(name: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((SCHEMAS / f"{name}.v1.json").read_text(encoding="utf-8"))
    return document


@pytest.mark.parametrize(("name", "model"), CASES)
def test_golden_document_validates_against_the_model_and_keeps_its_version(name: str, model: type[BaseModel]) -> None:
    document = golden(name)
    assert document["schema_version"] == "1.0.0"
    parsed = model.model_validate(document)
    assert parsed.model_dump()["schema_version"] == "1.0.0"


@pytest.mark.parametrize(("name", "model"), CASES)
def test_golden_document_validates_against_the_committed_schema(name: str, model: type[BaseModel]) -> None:
    validator = jsonschema.Draft202012Validator(schema(name))
    errors = [error.message for error in validator.iter_errors(golden(name))]
    assert errors == []
