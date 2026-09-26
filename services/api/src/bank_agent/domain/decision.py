"""Policy decisions: the output of the deterministic policy evaluator (phase 06).

A ``Decision`` names every rule it evaluated, in order, with the rule version, the reason code, the parameters
used, and the clause references. It has no free-text reasoning field by design: decisions are explained by
rules, clauses, and records.
"""

import re
from enum import StrEnum
from typing import Annotated, Self

from pydantic import (
    Field,
    GetJsonSchemaHandler,
    PositiveInt,
    StrictBool,
    StrictInt,
    StringConstraints,
    model_serializer,
    model_validator,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from bank_agent.domain.actions import ActionKind
from bank_agent.domain.base import Code, DomainModel
from bank_agent.domain.money import Money
from bank_agent.domain.workflow import StateName

CLAUSE_FAMILIES = ("SCOPE", "AUTH", "PRV", "DSP", "CRD", "ESC", "INF")
CLAUSE_JURISDICTIONS = ("MX", "CO", "AR", "ALL")
CLAUSE_ID_PATTERN = rf"^({'|'.join(CLAUSE_FAMILIES)})-({'|'.join(CLAUSE_JURISDICTIONS)})-[0-9]+(\.[0-9]+)*$"
CLAUSE_REF_PATTERN = CLAUSE_ID_PATTERN[:-1] + "@[1-9][0-9]*$"
RULE_ID_PATTERN = r"^[A-Z]+\.[a-z][a-z0-9_]*$"

ClauseId = Annotated[str, StringConstraints(pattern=CLAUSE_ID_PATTERN)]
RuleId = Annotated[str, StringConstraints(pattern=RULE_ID_PATTERN)]


class DecisionKind(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_CONFIRMATION = "require_confirmation"
    REQUIRE_STEP_UP = "require_step_up"
    CLARIFY = "clarify"
    ESCALATE = "escalate"
    ABSTAIN = "abstain"
    REFUSE = "refuse"


class ClauseRef(DomainModel):
    """A policy clause at an exact version, serialized as ``DSP-CO-2.1@3``. Language twins share the reference."""

    clause_id: ClauseId
    version: PositiveInt

    @model_validator(mode="before")
    @classmethod
    def _parse_string(cls, value: object) -> object:
        if isinstance(value, str):
            clause_id, separator, version = value.rpartition("@")
            if not separator or not re.fullmatch(r"[1-9][0-9]*", version):
                raise ValueError("a clause reference has the form CLAUSE-ID@version")
            return {"clause_id": clause_id, "version": int(version)}
        return value

    @model_serializer(mode="plain", when_used="always")
    def _serialize(self) -> str:
        return str(self)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler, /) -> JsonSchemaValue:
        return {"type": "string", "pattern": CLAUSE_REF_PATTERN, "title": "ClauseRef"}

    @classmethod
    def parse(cls, value: str) -> Self:
        return cls.model_validate(value)

    @property
    def family(self) -> str:
        return self.clause_id.split("-", 1)[0]

    def __str__(self) -> str:
        return f"{self.clause_id}@{self.version}"


ParamValue = StrictInt | StrictBool | Money | Annotated[str, StringConstraints(max_length=200)] | list[str]
"""A rule or clause parameter. No float and no bare Decimal, so a JSON round trip is lossless."""


class RuleResult(DomainModel):
    """The outcome of one rule. A failed rule names the effect it asks the evaluator to apply."""

    rule_id: RuleId
    rule_version: PositiveInt
    passed: bool
    effect: DecisionKind | None = None
    reason_code: Code
    params: dict[Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")], ParamValue] = Field(
        default_factory=dict
    )
    clause_refs: tuple[ClauseRef, ...] = ()
    missing_facts: tuple[Code, ...] = ()

    @model_validator(mode="after")
    def _validate_effect(self) -> Self:
        if self.passed and self.effect is not None:
            raise ValueError("a passed rule has no effect")
        if not self.passed and self.effect is None:
            raise ValueError("a failed rule must name its effect")
        if self.passed and self.missing_facts:
            raise ValueError("a rule with missing facts cannot pass")
        return self


def ordered_clause_union(results: tuple[RuleResult, ...]) -> tuple[ClauseRef, ...]:
    """The clause references of ``results`` in order of first appearance, without duplicates."""
    seen: dict[ClauseRef, None] = {}
    for result in results:
        for ref in result.clause_refs:
            seen.setdefault(ref, None)
    return tuple(seen)


class Decision(DomainModel):
    """Version 1 of the decision contract (``contracts/schemas/decision.v1.json``)."""

    schema_version: Annotated[str, StringConstraints(pattern=r"^1\.[0-9]+\.[0-9]+$")] = "1.0.0"
    state: StateName
    action: ActionKind | None = None
    kind: DecisionKind
    rule_results: tuple[RuleResult, ...]
    decisive_rule_ids: tuple[RuleId, ...] = ()
    clause_refs: tuple[ClauseRef, ...]
    policy_pack_version: Annotated[str, StringConstraints(min_length=1, max_length=128)]

    @model_validator(mode="after")
    def _validate_consistency(self) -> Self:
        evaluated = {result.rule_id for result in self.rule_results}
        unknown = [rule_id for rule_id in self.decisive_rule_ids if rule_id not in evaluated]
        if unknown:
            raise ValueError("every decisive rule must appear in rule_results")
        if self.clause_refs != ordered_clause_union(self.rule_results):
            raise ValueError("clause_refs must be the ordered union of the rule results' clause references")
        return self

    @classmethod
    def build(
        cls,
        *,
        state: str,
        kind: DecisionKind,
        rule_results: tuple[RuleResult, ...],
        policy_pack_version: str,
        action: ActionKind | None = None,
        decisive_rule_ids: tuple[str, ...] = (),
    ) -> Self:
        """Build a decision whose ``clause_refs`` is derived from the rule results."""
        return cls(
            state=state,
            action=action,
            kind=kind,
            rule_results=rule_results,
            decisive_rule_ids=decisive_rule_ids,
            clause_refs=ordered_clause_union(rule_results),
            policy_pack_version=policy_pack_version,
        )
