"""Each contract file's ``x-schema-version`` matches the version its model stamps on new documents."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "generate_contracts.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_contracts", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_contracts"] = module
    spec.loader.exec_module(module)
    return module


contracts = _load()


@pytest.mark.parametrize("contract", contracts.CONTRACTS, ids=lambda contract: contract.file_name)
def test_file_version_matches_the_model_default(contract: Any) -> None:
    field = contract.model.model_fields.get("schema_version")
    if field is None:
        assert contract.file_name == "policy_clause.v1.json"
        return
    assert field.default == contract.version


def test_output_contracts_share_the_new_release_and_input_contracts_remain_pinned() -> None:
    versions = {contract.file_name: contract.version for contract in contracts.CONTRACTS}
    assert versions == {
        "handoff.v1.json": "1.5.0",
        "execution_record.v1.json": "1.5.0",
        "decision.v1.json": "1.5.0",
        "scenario.v1.json": "1.4.0",
        "policy_clause.v1.json": "1.4.0",
    }
