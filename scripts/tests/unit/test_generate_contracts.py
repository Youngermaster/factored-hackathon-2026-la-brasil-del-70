import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "generate_contracts.py"
REASONING_NAMES = {
    "reasoning",
    "rationale",
    "thought",
    "thoughts",
    "chain_of_thought",
    "cot",
    "scratchpad",
    "inner_monologue",
}


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_contracts", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_contracts"] = module
    spec.loader.exec_module(module)
    return module


contracts = _load()


def _property_names(node: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(node, dict):
        properties = node.get("properties")
        if isinstance(properties, dict):
            names.update(properties)
        for value in node.values():
            names |= _property_names(value)
    elif isinstance(node, list):
        for value in node:
            names |= _property_names(value)
    return names


def test_committed_schemas_are_up_to_date() -> None:
    stale = contracts.stale_files(contracts.DEFAULT_OUTPUT)
    assert stale == [], f"stale contract schemas {stale}: run `make contracts` and commit the result"


def test_every_expected_contract_is_generated() -> None:
    names = [contract.file_name for contract in contracts.CONTRACTS]
    assert names == [
        "handoff.v1.json",
        "execution_record.v1.json",
        "decision.v1.json",
        "scenario.v1.json",
        "policy_clause.v1.json",
    ]


@pytest.mark.parametrize("contract", contracts.CONTRACTS, ids=lambda contract: contract.file_name)
def test_schema_header_and_strictness(contract: Any) -> None:
    document = json.loads(contracts.render(contract))
    assert document["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert document["$id"].endswith(contract.file_name)
    assert document["x-schema-version"] == contract.version
    assert document["additionalProperties"] is False


@pytest.mark.parametrize("file_name", ["handoff.v1.json", "execution_record.v1.json", "decision.v1.json"])
def test_output_contracts_have_no_reasoning_field(file_name: str) -> None:
    contract = next(c for c in contracts.CONTRACTS if c.file_name == file_name)
    names = _property_names(json.loads(contracts.render(contract)))
    assert names
    assert not names & REASONING_NAMES


def test_output_contracts_render_references_and_amounts_as_strings() -> None:
    handoff = json.loads(contracts.render(contracts.CONTRACTS[0]))
    assert handoff["$defs"]["ClauseRef"]["type"] == "string"
    assert handoff["$defs"]["SourceRef"]["type"] == "string"
    record = json.loads(contracts.render(contracts.CONTRACTS[1]))
    assert record["properties"]["cost_usd"]["type"] == "string"


def test_check_mode_reports_missing_and_stale_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert contracts.main(["--check", "--output-dir", str(tmp_path)]) == 1
    assert "handoff.v1.json is stale or missing" in capsys.readouterr().out
    assert contracts.main(["--output-dir", str(tmp_path)]) == 0
    assert "wrote 5 schema(s), 5 changed" in capsys.readouterr().out
    assert contracts.main(["--check", "--output-dir", str(tmp_path)]) == 0
    (tmp_path / "decision.v1.json").write_text("{}\n", encoding="utf-8")
    assert contracts.main(["--check", "--output-dir", str(tmp_path)]) == 1
    assert "decision.v1.json" in capsys.readouterr().out
    assert contracts.write_all(tmp_path) == ["decision.v1.json"]
