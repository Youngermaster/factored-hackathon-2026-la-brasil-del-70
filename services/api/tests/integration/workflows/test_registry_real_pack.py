"""The real definitions against the real pack: startup validation, complete transition tables, and schemas."""

import json
from pathlib import Path

import pytest

from bank_agent.application.engine.definition import WorkflowDefinition
from bank_agent.application.engine.handoff import handoff_schema
from bank_agent.application.engine.registry import build_registry
from bank_agent.application.workflows.baseline.definitions import BASELINE_DEFINITIONS
from bank_agent.bootstrap.workflows import PROPOSED_DEFINITIONS
from bank_agent.domain.actions import WRITE_TOOLS, ToolName
from bank_agent.domain.errors import WorkflowRegistryError, WorkflowTransitionError
from bank_agent.domain.workflow import WorkflowId
from bank_agent.domain.workflow_catalog import WORKFLOW_CATALOG
from bank_agent_workflow_support import Backend
from bank_agent_workflows import build_harness, shared_policy

SCHEMA = Path(__file__).resolve().parents[5] / "contracts" / "schemas" / "handoff.v1.json"
DEFINITIONS = [factory() for factory in (*PROPOSED_DEFINITIONS.values(), *BASELINE_DEFINITIONS.values())]
ENABLED = frozenset(WorkflowId)


@pytest.mark.parametrize("definition", DEFINITIONS, ids=lambda d: f"{d.variant}-{d.workflow}")
def test_every_move_outside_each_real_table_raises(definition: WorkflowDefinition) -> None:
    for source in definition.states:
        for target in definition.states:
            if definition.allows(source, target):
                definition.check_transition(source, target)
            else:
                with pytest.raises(WorkflowTransitionError):
                    definition.check_transition(source, target)


def test_the_real_registries_validate_against_the_pack_bindings_and_matrix() -> None:
    policy, grounding = shared_policy()
    for factories in (PROPOSED_DEFINITIONS, BASELINE_DEFINITIONS):
        definitions = {workflow: factory() for workflow, factory in factories.items()}
        registry = build_registry(
            "test", definitions, catalog=WORKFLOW_CATALOG, bound=grounding.bound, pack=policy.pack, enabled=ENABLED
        )
        assert registry.ordered_enabled() == tuple(WorkflowId)


def test_enabling_a_workflow_without_a_definition_stops_startup() -> None:
    policy, grounding = shared_policy()
    definitions: dict[WorkflowId, WorkflowDefinition] = {
        w: f() for w, f in PROPOSED_DEFINITIONS.items() if w is not WorkflowId.CREDIT
    }
    with pytest.raises(WorkflowRegistryError, match="credit is enabled but has no definition"):
        build_registry(
            "test", definitions, catalog=WORKFLOW_CATALOG, bound=grounding.bound, pack=policy.pack, enabled=ENABLED
        )


def test_account_inquiry_is_read_only_in_every_variant() -> None:
    for definition in DEFINITIONS:
        if definition.workflow is WorkflowId.ACCOUNT_INQUIRY:
            assert "EXECUTE" not in definition.states
            for spec in definition.states.values():
                assert not spec.allowed_tools & WRITE_TOOLS, spec.name
                assert not spec.action_policy_states, spec.name


def test_no_state_allowlist_reaches_the_credit_profile() -> None:
    for definition in DEFINITIONS:
        for spec in definition.states.values():
            assert ToolName.GET_MY_CREDIT_PROFILE not in spec.allowed_tools


def test_a_cut_workflow_is_out_of_scope(memory_only: Backend) -> None:
    harness = build_harness(memory_only.uow_factory, memory_only.session_store, enabled=("dispute",))
    assert harness.engine.registry.owner(WORKFLOW_CATALOG.descriptor(WorkflowId.CARD_SUPPORT).intents[0]) is None


def test_the_runtime_handoff_schema_is_the_committed_contract() -> None:
    committed = json.loads(SCHEMA.read_text(encoding="utf-8"))
    for header in ("$schema", "$id", "x-schema-version"):
        committed.pop(header)
    assert handoff_schema() == committed
