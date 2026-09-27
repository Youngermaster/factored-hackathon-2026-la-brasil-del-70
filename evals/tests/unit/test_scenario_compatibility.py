"""A scenario stored under version 1.0.0 of the scenario contract stays valid under every later 1.x version."""

import json
from pathlib import Path
from typing import Any

import jsonschema

from bank_evals.scenarios.model import Scenario

TESTS = Path(__file__).resolve().parents[1]
REPOSITORY = TESTS.parents[1]
GOLDEN = TESTS / "fixtures" / "contracts" / "v1.0.0" / "scenario.json"
SCHEMA = REPOSITORY / "contracts" / "schemas" / "scenario.v1.json"


def _load(path: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return document


def test_golden_scenario_validates_against_the_model_and_keeps_its_version() -> None:
    scenario = Scenario.model_validate(_load(GOLDEN))
    assert scenario.schema_version == "1.0.0"


def test_golden_scenario_validates_against_the_committed_schema() -> None:
    validator = jsonschema.Draft202012Validator(_load(SCHEMA))
    assert [error.message for error in validator.iter_errors(_load(GOLDEN))] == []
