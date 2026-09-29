#!/usr/bin/env python3
"""Generate the cross-boundary JSON Schemas in ``contracts/schemas/`` from the Pydantic models.

Usage:
    uv run --frozen python scripts/generate_contracts.py                 write every schema
    uv run --frozen python scripts/generate_contracts.py --check         exit 1 and name stale or missing files
    uv run --frozen python scripts/generate_contracts.py --output-dir D  use another directory

The models are the single source of truth. Output contracts (documents the system produces) are generated in
serialization mode, so a ``model_dump(mode="json")`` document matches them; input contracts (documents people
and generators author) in validation mode. Each file gets ``$schema``, ``$id``, and ``x-schema-version``.
The versioning rules are in ``contracts/README.md``. ``make contracts`` runs this script, and a unit test
fails when the committed files are stale.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from bank_agent.domain.decision import Decision
from bank_agent.domain.execution_record import ExecutionRecord
from bank_agent.domain.handoff import Handoff
from bank_agent.domain.policy import ClauseMetadata
from bank_evals.scenarios.model import Scenario

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPOSITORY_ROOT / "contracts" / "schemas"
SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_BASE_URI = "https://bank-agent.local/contracts/schemas/"


@dataclass(frozen=True)
class Contract:
    file_name: str
    model: type[BaseModel]
    mode: Literal["validation", "serialization"]
    version: str


CONTRACTS = (
    Contract("handoff.v1.json", Handoff, "serialization", "1.3.0"),
    Contract("execution_record.v1.json", ExecutionRecord, "serialization", "1.3.0"),
    Contract("decision.v1.json", Decision, "serialization", "1.3.0"),
    Contract("scenario.v1.json", Scenario, "validation", "1.3.0"),
    Contract("policy_clause.v1.json", ClauseMetadata, "validation", "1.3.0"),
)


def render(contract: Contract) -> str:
    """The exact file content for ``contract``: pretty JSON with a trailing newline."""
    schema = contract.model.model_json_schema(mode=contract.mode)
    document = {
        "$schema": SCHEMA_DIALECT,
        "$id": f"{SCHEMA_BASE_URI}{contract.file_name}",
        "x-schema-version": contract.version,
        **schema,
    }
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def stale_files(directory: Path) -> list[str]:
    """Names of contract files in ``directory`` that are missing or differ from the models."""
    stale: list[str] = []
    for contract in CONTRACTS:
        path = directory / contract.file_name
        if not path.is_file() or path.read_text(encoding="utf-8") != render(contract):
            stale.append(contract.file_name)
    return stale


def write_all(directory: Path) -> list[str]:
    """Write every contract to ``directory`` and return the names of files that changed."""
    directory.mkdir(parents=True, exist_ok=True)
    changed = stale_files(directory)
    for contract in CONTRACTS:
        (directory / contract.file_name).write_text(render(contract), encoding="utf-8")
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="report stale files instead of writing them")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    if args.check:
        stale = stale_files(args.output_dir)
        for name in stale:
            print(f"generate-contracts: {name} is stale or missing; run `make contracts`")
        return 1 if stale else 0
    changed = write_all(args.output_dir)
    print(f"generate-contracts: wrote {len(CONTRACTS)} schema(s), {len(changed)} changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
