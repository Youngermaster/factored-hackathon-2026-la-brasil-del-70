"""Bound lookup over the real pack: every state of every workflow in ``bindings.yaml``, country, and language."""

import pytest
import yaml

from bank_agent.adapters.policy.filesystem import FilesystemPolicyRepository
from bank_agent.application.grounding.bound import BoundPolicyLookup
from bank_agent.bootstrap.settings import DEFAULT_POLICY_DIR
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.policy import Jurisdiction
from bank_agent.domain.workflow import WorkflowId
from bank_agent.domain.workflow_catalog import WORKFLOW_CATALOG
from bank_agent_builders import customer

REPOSITORY = FilesystemPolicyRepository.from_directory(DEFAULT_POLICY_DIR)
LOOKUP = BoundPolicyLookup(REPOSITORY)
BINDINGS = yaml.safe_load((DEFAULT_POLICY_DIR / "bindings.yaml").read_text(encoding="utf-8"))
CASES = [
    (WorkflowId(workflow), state, country, language)
    for workflow, states in BINDINGS["workflows"].items()
    for state in states
    for country in Country
    for language in Language
]


def test_bindings_list_exactly_the_registered_states() -> None:
    for descriptor in WORKFLOW_CATALOG.descriptors:
        assert tuple(BINDINGS["workflows"][descriptor.id.value]) == descriptor.states


@pytest.mark.parametrize(("workflow", "state", "country", "language"), CASES)
def test_every_state_resolves_to_the_exact_bound_clauses(
    workflow: WorkflowId, state: str, country: Country, language: Language
) -> None:
    bound = LOOKUP.for_state(workflow, state, customer(country=country), language)
    templates = [*BINDINGS["common"], *BINDINGS["workflows"][workflow.value][state]["clauses"]]
    expected = list(dict.fromkeys(t.replace("{country}", country.value) for t in templates))
    assert [ref.clause_id for ref in bound.refs] == expected
    for clause in bound.clauses:
        assert clause.metadata.language is language
        assert clause.metadata.jurisdiction in {Jurisdiction(country.value), Jurisdiction.ALL}
        assert clause.metadata.version == REPOSITORY.get_clause(clause.metadata.clause_id, language).metadata.version
    assert bound.pack_version == REPOSITORY.pack_version()
