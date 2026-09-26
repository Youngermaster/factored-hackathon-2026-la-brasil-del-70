"""Policy clauses and action requirements, as stored in the policy pack (``policies/``, phase 06).

``ClauseMetadata`` is the validated front matter of one clause file in one language; its JSON Schema is
``contracts/schemas/policy_clause.v1.json``. ``PolicyClause`` adds the customer-facing body, whose ``{param}``
placeholders are filled from ``params``. Amount parameters are ``{"amount": "500", "currency": "USD"}``
objects, so no amount is ever read from YAML as a float.
"""

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, PositiveInt, StringConstraints, model_validator

from bank_agent.domain.access import AuthLevel
from bank_agent.domain.actions import ActionKind
from bank_agent.domain.base import DomainModel
from bank_agent.domain.decision import ClauseId, ClauseRef, ParamValue, RuleId
from bank_agent.domain.locale import Language
from bank_agent.domain.workflow import StateName


class ClauseFamily(StrEnum):
    SCOPE = "SCOPE"
    AUTH = "AUTH"
    PRV = "PRV"
    DSP = "DSP"
    CRD = "CRD"
    ESC = "ESC"
    INF = "INF"


class Jurisdiction(StrEnum):
    MX = "MX"
    CO = "CO"
    AR = "AR"
    ALL = "ALL"


ParamName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]


class ClauseMetadata(DomainModel):
    """Front matter of one clause file. Version 1 of the policy clause contract."""

    clause_id: ClauseId
    version: PositiveInt
    jurisdiction: Jurisdiction
    language: Language
    effective_from: date
    synthetic: Literal[True]
    params: dict[ParamName, ParamValue] = Field(default_factory=dict)
    bound_rules: tuple[RuleId, ...] = ()
    summary: Annotated[str, StringConstraints(min_length=1, max_length=300)]

    @model_validator(mode="after")
    def _validate_id(self) -> Self:
        if self.clause_id.split("-")[1] != self.jurisdiction.value:
            raise ValueError("the jurisdiction must match the jurisdiction segment of the clause id")
        return self

    @property
    def family(self) -> ClauseFamily:
        return ClauseFamily(self.clause_id.split("-", 1)[0])

    @property
    def ref(self) -> ClauseRef:
        return ClauseRef(clause_id=self.clause_id, version=self.version)


class PolicyClause(DomainModel):
    metadata: ClauseMetadata
    body: Annotated[str, StringConstraints(min_length=1, max_length=5000)]

    @property
    def ref(self) -> ClauseRef:
        return self.metadata.ref


class ActionRequirement(DomainModel):
    """One row of ``policies/matrix.yaml``."""

    action: ActionKind
    requires_confirmation: bool
    required_auth_level: AuthLevel
    requires_step_up: bool
    allowed_states: tuple[StateName, ...]
