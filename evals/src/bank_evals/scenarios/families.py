"""Scenario families: situations with shared expected behavior, each with phrasings in es and pt.

A situation (``Situation``) states what the customer wants and what the policy expects: the outcome, the database
end state, the disclosures, the handoff fields. Its phrasings (``Phrasing``) are the words: Spanish (with an
optional Argentine voseo variant) and Portuguese. The template family of a scenario is one phrasing of one
situation, and a family belongs wholly to one split, so dev and test never share a phrasing while the labels
come from the same situation.

The situations live in ``family_data/<workflow>.yaml`` next to this module, written by the team. Texts may name
persona facts in braces (``{recent_amount}``), filled from the evaluation world when a scenario is rendered.
"""

from __future__ import annotations

from functools import cache
from importlib.resources import files
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from bank_agent.domain.eligibility import EligibilityOutcome
from bank_agent.domain.workflow import WorkflowId
from bank_evals.scenarios.model import ExpectedOutcome, Provenance, ScenarioCategory

FAMILY_FILES = ("account_inquiry", "card_support", "dispute", "credit", "routing")
TurnSpec = str | dict[str, Any]


class Phrasing(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    es: list[TurnSpec]
    es_ar: list[TurnSpec] | None = Field(default=None, alias="es-AR")
    pt: list[TurnSpec]


class Situation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    category: ScenarioCategory
    role: str
    goal: str
    expected_outcome: ExpectedOutcome
    workflow: WorkflowId | None = None
    in_scope: bool = True
    assertions: list[dict[str, Any]] = Field(default_factory=list)
    required: list[dict[str, Any]] = Field(default_factory=list)
    forbidden: list[dict[str, Any]] = Field(default_factory=list)
    handoff_fields: list[str] = Field(default_factory=list)
    fixtures: list[dict[str, Any]] = Field(default_factory=list)
    tool_failure_plan: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    known_facts: dict[str, str] = Field(default_factory=dict)
    hidden_facts: dict[str, str] = Field(default_factory=dict)
    simulate: str | None = None
    expected_workflow_path: list[WorkflowId] = Field(default_factory=list)
    eligibility: EligibilityOutcome | None = None
    provenance: Provenance | None = None
    countries: list[str] = Field(default_factory=lambda: ["MX", "CO", "AR"])
    phrasings: list[Phrasing]

    def family_key(self, workflow: str, index: int) -> str:
        return f"{workflow[:3]}.{self.category.value[:6]}.{self.key}.{index + 1}"[:63]


@cache
def load_situations(name: str) -> tuple[Situation, ...]:
    """The situations of one family file (``account_inquiry``, ``card_support``, ``dispute``, ``credit``,
    ``routing``); a workflow file's situations default to its workflow."""
    source = files("bank_evals.scenarios").joinpath("family_data", f"{name}.yaml")
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    situations = []
    for item in raw:
        if name != "routing":
            item.setdefault("workflow", name)
        situations.append(Situation.model_validate(item))
    keys = [s.key for s in situations]
    if len(set(keys)) != len(keys):
        raise ValueError(f"{name}: duplicate situation keys")
    return tuple(situations)


def all_situations() -> dict[str, tuple[Situation, ...]]:
    return {name: load_situations(name) for name in FAMILY_FILES}
