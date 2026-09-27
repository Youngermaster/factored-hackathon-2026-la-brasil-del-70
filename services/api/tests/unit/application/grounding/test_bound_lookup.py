"""Bound clause lookup over the in-memory fixture pack."""

import pytest

from bank_agent.application.grounding.bound import BoundPolicyLookup
from bank_agent.domain.errors import PolicyBindingMissingError
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.workflow import WorkflowId
from bank_agent.domain.workflow_catalog import WORKFLOW_CATALOG, WorkflowCatalog
from bank_agent_builders import customer
from bank_agent_policy import FIXTURE_BINDINGS, fixture_pack

FIXTURE_CATALOG = WorkflowCatalog(
    descriptors=tuple(
        descriptor.model_copy(update={"states": tuple(FIXTURE_BINDINGS.workflows[descriptor.id])})
        for descriptor in WORKFLOW_CATALOG.descriptors
    )
)


def lookup() -> BoundPolicyLookup:
    return BoundPolicyLookup(fixture_pack(), catalog=FIXTURE_CATALOG, countries=(Country.MX,))


def test_returns_common_then_state_clauses_for_the_customer_country() -> None:
    bound = lookup().for_state(WorkflowId.DISPUTE, "COLLECT_DETAILS", customer(country=Country.MX), Language.PT)
    ids = [clause.metadata.clause_id for clause in bound.clauses]
    assert ids == ["SCOPE-ALL-1", "AUTH-ALL-1", "PRV-ALL-1", "ESC-ALL-1", "DSP-ALL-1", "DSP-MX-1", "DSP-MX-3"]
    assert {clause.metadata.language for clause in bound.clauses} == {Language.PT}
    assert bound.jurisdiction is Country.MX
    assert bound.pack_version == "pack-fixture-0001"
    assert [ref.clause_id for ref in bound.refs] == ids


def test_the_jurisdiction_follows_the_verified_customer_record() -> None:
    bound = lookup().for_state(WorkflowId.DISPUTE, "CREATE_CASE", customer(country=Country.MX), Language.ES)
    assert "DSP-MX-1" in [ref.clause_id for ref in bound.refs]
    assert bound.params("DSP-MX-1")["dispute_window_days"] == 90


def test_a_country_that_was_not_resolved_at_construction_is_refused() -> None:
    with pytest.raises(PolicyBindingMissingError, match="no binding"):
        lookup().for_state(WorkflowId.DISPUTE, "CREATE_CASE", customer(country=Country.AR), Language.ES)


def test_a_clause_outside_the_binding_is_refused() -> None:
    bound = lookup().for_state(WorkflowId.CREDIT, "START", customer(), Language.ES)
    with pytest.raises(PolicyBindingMissingError, match="not bound"):
        bound.clause("DSP-MX-1")


def test_an_unregistered_state_is_refused_at_runtime() -> None:
    with pytest.raises(PolicyBindingMissingError, match="NOT_A_STATE"):
        lookup().for_state(WorkflowId.CREDIT, "NOT_A_STATE", customer(), Language.ES)


def test_a_registered_state_without_a_binding_fails_at_construction() -> None:
    with pytest.raises(PolicyBindingMissingError, match="incomplete bound policy") as error:
        BoundPolicyLookup(fixture_pack())
    assert "account_inquiry.IDENTIFY_PRODUCT" in str(error.value)
    assert "and " in str(error.value)
