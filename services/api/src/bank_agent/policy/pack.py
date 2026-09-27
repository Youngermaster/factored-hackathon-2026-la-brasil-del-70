"""The validated, in-memory policy pack, and the ``PolicyRepository`` it implements.

``policy.loader`` builds a ``PolicyPack`` from the text of the files under ``policies/``; the filesystem
adapter only reads those files. Everything here is pure: lookups over immutable data.
"""

from collections.abc import Mapping, Sequence
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from bank_agent.domain.access import AuthLevel
from bank_agent.domain.actions import ActionKind
from bank_agent.domain.base import DomainModel
from bank_agent.domain.decision import ParamValue
from bank_agent.domain.errors import PolicyBindingMissingError, PolicyClauseNotFoundError, PolicyPackInvalidError
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.policy import ActionRequirement, Jurisdiction, PolicyClause
from bank_agent.domain.workflow import StateName, WorkflowId

COUNTRY_TEMPLATE = "{country}"
ClauseTemplate = Annotated[str, StringConstraints(pattern=r"^[A-Z]+-([A-Z]{2,3}|\{country\})-[0-9]+(\.[0-9]+)*$")]
"""A clause id in a binding; ``{country}`` resolves from the verified customer profile, never from text."""


class PackInfo(DomainModel):
    """``policies/pack.yaml``."""

    pack_id: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]{0,63}$")]
    label: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    synthetic: Literal[True]
    supported_workflows: Annotated[tuple[WorkflowId, ...], Field(min_length=1)]
    languages: tuple[Language, ...]


class StateBinding(DomainModel):
    """One state of one workflow: the authentication it needs and the clauses it depends on."""

    auth: AuthLevel
    clauses: Annotated[tuple[ClauseTemplate, ...], Field(min_length=1)]


class Bindings(DomainModel):
    """``policies/bindings.yaml``: clauses common to every state, then workflow, then state."""

    common: tuple[ClauseTemplate, ...]
    workflows: dict[WorkflowId, dict[StateName, StateBinding]]

    def binding(self, workflow: WorkflowId, state: str) -> StateBinding:
        try:
            return self.workflows[workflow][state]
        except KeyError:
            raise PolicyBindingMissingError(f"no binding for state {state} of workflow {workflow}") from None

    def clause_ids(self, workflow: WorkflowId, state: str, jurisdiction: Country) -> tuple[str, ...]:
        """Common and state clause ids with ``{country}`` resolved, in binding order, without duplicates."""
        templates = (*self.common, *self.binding(workflow, state).clauses)
        resolved = (template.replace(COUNTRY_TEMPLATE, jurisdiction.value) for template in templates)
        return tuple(dict.fromkeys(resolved))


class PolicyPack:
    """Clauses by id, language, and version; bindings; the action matrix; and the eligibility messages.

    It implements the ``PolicyRepository`` port. ``clauses`` maps ``(clause_id, language)`` to every known
    version in ascending order; the last one is current.
    """

    def __init__(
        self,
        *,
        version: str,
        info: PackInfo,
        clauses: Mapping[tuple[str, Language], Sequence[PolicyClause]],
        bindings: Bindings,
        matrix: Mapping[ActionKind, ActionRequirement],
        messages: Mapping[Language, Mapping[str, Mapping[str, str]]],
    ) -> None:
        self.version = version
        self.info = info
        self._clauses = {key: tuple(versions) for key, versions in clauses.items()}
        self.bindings = bindings
        self._matrix = dict(matrix)
        self._messages = {language: {k: dict(v) for k, v in groups.items()} for language, groups in messages.items()}

    # --- PolicyRepository ------------------------------------------------------------------------------------

    def pack_version(self) -> str:
        return self.version

    def get_clause(self, clause_id: str, language: Language, version: int | None = None) -> PolicyClause:
        versions = self._clauses.get((clause_id, language), ())
        if not versions:
            raise PolicyClauseNotFoundError(f"unknown clause {clause_id} in {language}")
        if version is None:
            return versions[-1]
        for clause in versions:
            if clause.metadata.version == version:
                return clause
        raise PolicyClauseNotFoundError(f"unknown version {version} of clause {clause_id}")

    def get_bound(
        self, workflow: WorkflowId, state: str, jurisdiction: Country, language: Language
    ) -> Sequence[PolicyClause]:
        clause_ids = self.bindings.clause_ids(workflow, state, jurisdiction)
        return tuple(self.get_clause(clause_id, language) for clause_id in clause_ids)

    def list_clauses(
        self, language: Language | None = None, jurisdiction: Country | None = None
    ) -> Sequence[PolicyClause]:
        allowed = None if jurisdiction is None else {Jurisdiction(jurisdiction.value), Jurisdiction.ALL}
        current = (versions[-1] for versions in self._clauses.values())
        selected = [
            clause
            for clause in current
            if (language is None or clause.metadata.language is language)
            and (allowed is None or clause.metadata.jurisdiction in allowed)
        ]
        return sorted(selected, key=lambda clause: (clause.metadata.clause_id, clause.metadata.language.value))

    def action_requirements(self, action: ActionKind) -> ActionRequirement:
        try:
            return self._matrix[action]
        except KeyError:
            raise PolicyPackInvalidError(f"the action matrix has no row for {action}") from None

    # --- Pack helpers ----------------------------------------------------------------------------------------

    def clause_ids(self) -> tuple[str, ...]:
        return tuple(sorted({clause_id for clause_id, _ in self._clauses}))

    def params(self, clause_id: str) -> Mapping[str, ParamValue]:
        """The current parameters of a clause; identical in every language by the parity check."""
        return self.get_clause(clause_id, Language.ES).metadata.params

    def message(self, language: Language, group: str, key: str) -> str:
        try:
            return self._messages[language][group][key]
        except KeyError:
            raise PolicyPackInvalidError(f"no {language} message {group}.{key}") from None
