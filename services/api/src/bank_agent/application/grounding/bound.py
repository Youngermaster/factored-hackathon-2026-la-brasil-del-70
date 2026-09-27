"""Bound policy: the clauses a workflow state depends on, fetched by id, never by open retrieval.

``BoundPolicyLookup`` resolves every registered state of every workflow, for every country and language, when it
is built, so a missing binding or clause is a startup error rather than a runtime surprise. At runtime the
jurisdiction comes only from the verified customer record, never from text.
"""

from collections.abc import Iterable, Mapping

from bank_agent.domain.base import DomainModel
from bank_agent.domain.customer import Customer
from bank_agent.domain.decision import ClauseRef, ParamValue
from bank_agent.domain.errors import ConfigurationError, PolicyBindingMissingError
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.policy import PolicyClause
from bank_agent.domain.workflow import StateName, WorkflowId
from bank_agent.domain.workflow_catalog import WORKFLOW_CATALOG, WorkflowCatalog
from bank_agent.ports.policy import PolicyRepository

MAX_REPORTED_PROBLEMS = 10


class BoundPolicy(DomainModel):
    """The clauses bound to one state of one workflow, in binding order, for one jurisdiction and language."""

    workflow: WorkflowId
    state: StateName
    jurisdiction: Country
    language: Language
    pack_version: str
    clauses: tuple[PolicyClause, ...]

    @property
    def refs(self) -> tuple[ClauseRef, ...]:
        return tuple(clause.ref for clause in self.clauses)

    def clause(self, clause_id: str) -> PolicyClause:
        for clause in self.clauses:
            if clause.metadata.clause_id == clause_id:
                return clause
        raise PolicyBindingMissingError(f"clause {clause_id} is not bound to {self.workflow}.{self.state}")

    def params(self, clause_id: str) -> Mapping[str, ParamValue]:
        return self.clause(clause_id).metadata.params


class BoundPolicyLookup:
    """Deterministic clause lookup by (workflow, state, verified jurisdiction, language)."""

    def __init__(
        self,
        repository: PolicyRepository,
        *,
        catalog: WorkflowCatalog = WORKFLOW_CATALOG,
        languages: Iterable[Language] = tuple(Language),
        countries: Iterable[Country] = tuple(Country),
    ) -> None:
        self._pack_version = repository.pack_version()
        self._bound: dict[tuple[WorkflowId, str, Country, Language], tuple[PolicyClause, ...]] = {}
        problems: list[str] = []
        languages, countries = tuple(languages), tuple(countries)
        for descriptor in catalog.descriptors:
            for state in descriptor.states:
                for country in countries:
                    for language in languages:
                        key = (descriptor.id, state, country, language)
                        try:
                            self._bound[key] = tuple(repository.get_bound(descriptor.id, state, country, language))
                        except ConfigurationError as error:
                            problems.append(f"{descriptor.id}.{state} ({country}, {language}): {error}")
        if problems:
            shown = "; ".join(problems[:MAX_REPORTED_PROBLEMS])
            more = len(problems) - MAX_REPORTED_PROBLEMS
            raise PolicyBindingMissingError(
                f"incomplete bound policy: {shown}" + (f"; and {more} more" if more > 0 else "")
            )

    @property
    def pack_version(self) -> str:
        return self._pack_version

    def covers(self, workflow: WorkflowId, state: str) -> bool:
        """True when ``state`` of ``workflow`` resolved for every country and language at construction."""
        keys = {(w, s, c, lang) for (w, s, c, lang) in self._bound if w is workflow and s == state}
        return bool(keys) and len(keys) == len({(c, lang) for (_, _, c, lang) in self._bound})

    def for_state(self, workflow: WorkflowId, state: str, customer: Customer, language: Language) -> BoundPolicy:
        """The clauses bound to ``state`` of ``workflow`` for the verified customer's jurisdiction."""
        clauses = self._bound.get((workflow, state, customer.country, language))
        if clauses is None:
            raise PolicyBindingMissingError(f"no binding for state {state} of workflow {workflow} in {language}")
        return BoundPolicy(
            workflow=workflow,
            state=state,
            jurisdiction=customer.country,
            language=language,
            pack_version=self._pack_version,
            clauses=clauses,
        )
