import re
from typing import Any

import pytest
from pydantic import ValidationError

from bank_agent.domain.actions import ActionKind
from bank_agent.domain.decision import CLAUSE_FAMILIES
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.handoff import EscalationReasonCode as ReexportedCode
from bank_agent.domain.policy import ClauseFamily
from bank_agent.domain.workflow import CROSS_WORKFLOW_INTENTS, Intent, WorkflowId, WorkflowRef
from bank_agent.domain.workflow_catalog import WORKFLOW_CATALOG, WorkflowCatalog, WorkflowDescriptor

WORKFLOW_REF_ID_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"


def descriptor(workflow: WorkflowId = WorkflowId.DISPUTE, **overrides: Any) -> WorkflowDescriptor:
    fields: dict[str, Any] = {
        "id": workflow,
        "version": 1,
        "intents": [Intent.DISPUTE_NEW],
        "entry_state": "START",
        "states": ["START", "ESCALATE"],
        "clause_families": [ClauseFamily.DSP],
    }
    return WorkflowDescriptor.model_validate({**fields, **overrides})


def test_every_intent_is_cross_workflow_or_owned_by_exactly_one_workflow() -> None:
    assert WORKFLOW_CATALOG.unowned_intents() == frozenset()
    for intent in Intent:
        owners = [d.id for d in WORKFLOW_CATALOG.descriptors if intent in d.intents]
        if intent in CROSS_WORKFLOW_INTENTS:
            assert owners == [], intent
        else:
            assert len(owners) == 1, intent


def test_the_entry_state_must_be_one_of_the_states() -> None:
    with pytest.raises(ValidationError, match="entry state"):
        descriptor(states=["ESCALATE"])


def test_states_must_not_repeat() -> None:
    with pytest.raises(ValidationError, match="states must not repeat"):
        descriptor(states=["START", "START"])


def test_every_workflow_starts_at_start_and_can_escalate() -> None:
    for item in WORKFLOW_CATALOG.descriptors:
        assert item.states[0] == item.entry_state == "START"
        assert "ESCALATE" in item.states


def test_the_catalog_names_the_four_workflows() -> None:
    assert WORKFLOW_CATALOG.ids() == tuple(WorkflowId)


@pytest.mark.parametrize("workflow", list(WorkflowId))
def test_workflow_ids_fit_the_workflow_ref_pattern(workflow: WorkflowId) -> None:
    assert re.fullmatch(WORKFLOW_REF_ID_PATTERN, workflow.value)
    assert WorkflowRef(id=workflow, version=1).id == workflow.value


def test_routes_intents_to_their_owner() -> None:
    assert WORKFLOW_CATALOG.workflow_for(Intent.CARD_BLOCK) is WorkflowId.CARD_SUPPORT
    assert WORKFLOW_CATALOG.workflow_for(Intent.BALANCE_INQUIRY) is WorkflowId.ACCOUNT_INQUIRY
    assert WORKFLOW_CATALOG.workflow_for(Intent.CREDIT_ELIGIBILITY) is WorkflowId.CREDIT
    assert WORKFLOW_CATALOG.workflow_for(Intent.DISPUTE_STATUS) is WorkflowId.DISPUTE
    assert WORKFLOW_CATALOG.workflow_for(Intent.HUMAN_REQUEST) is None


def test_card_support_and_dispute_may_block_cards() -> None:
    assert WORKFLOW_CATALOG.descriptor(WorkflowId.CARD_SUPPORT).write_actions == (ActionKind.BLOCK_CARD,)
    assert ActionKind.BLOCK_CARD in WORKFLOW_CATALOG.descriptor(WorkflowId.DISPUTE).write_actions
    assert WORKFLOW_CATALOG.descriptor(WorkflowId.ACCOUNT_INQUIRY).write_actions == ()
    assert set(WORKFLOW_CATALOG.descriptor(WorkflowId.CARD_SUPPORT).escalation_only_intents) == {
        Intent.CARD_UNBLOCK_REQUEST,
        Intent.CARD_REPLACEMENT_REQUEST,
    }


def test_descriptor_lookup_of_a_missing_workflow_raises() -> None:
    catalog = WorkflowCatalog(descriptors=(descriptor(),))
    with pytest.raises(KeyError):
        catalog.descriptor(WorkflowId.CREDIT)


def test_rejects_duplicate_workflow_ids() -> None:
    with pytest.raises(ValidationError, match="only once"):
        WorkflowCatalog(descriptors=(descriptor(), descriptor(intents=[Intent.DISPUTE_STATUS])))


def test_rejects_an_intent_owned_by_two_workflows() -> None:
    with pytest.raises(ValidationError, match="only one workflow"):
        WorkflowCatalog(descriptors=(descriptor(), descriptor(WorkflowId.CREDIT)))


def test_rejects_cross_workflow_and_unknown_intents() -> None:
    with pytest.raises(ValidationError, match="cross-workflow"):
        descriptor(intents=[Intent.DISPUTE_NEW, Intent.HUMAN_REQUEST])
    with pytest.raises(ValidationError):
        descriptor(intents=["loan_restructuring"])


def test_rejects_escalation_only_intents_the_workflow_does_not_own() -> None:
    with pytest.raises(ValidationError, match="escalation-only"):
        descriptor(escalation_only_intents=[Intent.CARD_UNBLOCK_REQUEST])


def test_rejects_repeated_values() -> None:
    with pytest.raises(ValidationError, match="must not repeat"):
        descriptor(intents=[Intent.DISPUTE_NEW, Intent.DISPUTE_NEW])


def test_a_partial_catalog_reports_unowned_intents() -> None:
    catalog = WorkflowCatalog(descriptors=(descriptor(),))
    assert Intent.CREDIT_ELIGIBILITY in catalog.unowned_intents()
    assert Intent.INFORMATIONAL not in catalog.unowned_intents()


def test_clause_family_enum_matches_the_clause_id_pattern_list() -> None:
    assert tuple(family.value for family in ClauseFamily) == CLAUSE_FAMILIES
    assert {"ACC", "CRE", "ELG"} <= set(CLAUSE_FAMILIES)


def test_escalation_codes_are_reexported_by_the_handoff_module() -> None:
    assert ReexportedCode is EscalationReasonCode
    assert EscalationReasonCode("eligibility_contested") is EscalationReasonCode.ELIGIBILITY_CONTESTED
