"""Registry validation at startup: every missing or inconsistent piece is a configuration error."""

import pytest

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.definition import StateKind, StateSpec, WorkflowDefinition, build_definition
from bank_agent.application.engine.registry import build_registry
from bank_agent.domain.actions import ActionKind, ToolName
from bank_agent.domain.errors import WorkflowRegistryError
from bank_agent.domain.policy import ActionRequirement
from bank_agent.domain.workflow import Intent, WorkflowId
from bank_agent.domain.workflow_catalog import WORKFLOW_CATALOG
from bank_agent_policy import FIXTURE_MATRIX

DSP = WorkflowId.DISPUTE


async def noop(ctx: TurnContext) -> Step:
    return Step(ctx.state)


class Coverage:
    def __init__(self, missing: frozenset[str] = frozenset()) -> None:
        self.missing = missing

    def covers(self, workflow: WorkflowId, state: str) -> bool:
        return state not in self.missing


class Matrix:
    def action_requirements(self, action: ActionKind) -> ActionRequirement:
        return FIXTURE_MATRIX[action]


DISPUTE_INTENTS = frozenset(WORKFLOW_CATALOG.descriptor(DSP).intents)


def dispute(*extra: StateSpec, intents: frozenset[Intent] = DISPUTE_INTENTS) -> WorkflowDefinition:
    states = (
        StateSpec(name="START", policy_state="START", handler=noop, kind=StateKind.ACCEPTS_REQUEST),
        StateSpec(
            name="EXECUTE",
            policy_state="CREATE_CASE",
            handler=noop,
            kind=StateKind.WORKING,
            allowed_tools=frozenset({ToolName.CREATE_DISPUTE_CASE}),
            action_policy_states={ActionKind.CREATE_DISPUTE_CASE: "CREATE_CASE"},
        ),
        *extra,
    )
    return build_definition(workflow=DSP, version=1, states=states, transitions={}, intents=intents)


def build(
    definitions: dict[WorkflowId, WorkflowDefinition], enabled: frozenset[WorkflowId], **coverage: object
) -> None:
    build_registry(
        "test",
        definitions,
        catalog=WORKFLOW_CATALOG,
        bound=Coverage(**coverage),  # type: ignore[arg-type]
        pack=Matrix(),
        enabled=enabled,
    )


def test_a_consistent_registry_builds() -> None:
    registry = build_registry(
        "test", {DSP: dispute()}, catalog=WORKFLOW_CATALOG, bound=Coverage(), pack=Matrix(), enabled=frozenset({DSP})
    )
    assert registry.ordered_enabled() == (DSP,)
    assert registry.owner(WORKFLOW_CATALOG.descriptor(DSP).intents[0]) is DSP


def test_an_enabled_workflow_without_a_definition_is_a_startup_error() -> None:
    with pytest.raises(WorkflowRegistryError, match="card_support is enabled but has no definition"):
        build({DSP: dispute()}, frozenset({DSP, WorkflowId.CARD_SUPPORT}))


def test_a_state_without_bindings_is_a_startup_error() -> None:
    with pytest.raises(WorkflowRegistryError, match="not bound for every country"):
        build({DSP: dispute()}, frozenset({DSP}), missing=frozenset({"CREATE_CASE"}))


def test_non_canonical_states_engine_only_tools_and_unmatched_writes_are_errors() -> None:
    wrong_state = StateSpec(name="X", policy_state="NOT_A_STATE", handler=noop, kind=StateKind.WORKING)
    engine_only = StateSpec(
        name="Y",
        policy_state="START",
        handler=noop,
        kind=StateKind.WORKING,
        allowed_tools=frozenset({ToolName.GET_MY_CREDIT_PROFILE, ToolName.BLOCK_CARD}),
    )
    disallowed = StateSpec(
        name="Z",
        policy_state="START",
        handler=noop,
        kind=StateKind.WORKING,
        action_policy_states={ActionKind.CREATE_DISPUTE_CASE: "START", ActionKind.SUBMIT_CREDIT_APPLICATION: "START"},
    )
    with pytest.raises(WorkflowRegistryError) as raised:
        build({DSP: dispute(wrong_state, engine_only, disallowed)}, frozenset({DSP}))
    message = str(raised.value)
    assert "NOT_A_STATE is not a canonical state" in message
    assert "get_my_credit_profile is engine only" in message
    assert "write tool block_card needs a policy state" in message
    assert "does not allow create_dispute_case in START" in message
    assert "may not perform submit_credit_application" in message


def test_intents_must_match_the_catalog_and_ids_must_match_definitions() -> None:
    with pytest.raises(WorkflowRegistryError, match="intents differ"):
        build({DSP: dispute(intents=frozenset())}, frozenset({DSP}))
    with pytest.raises(WorkflowRegistryError, match="registered with the definition"):
        build({WorkflowId.CARD_SUPPORT: dispute()}, frozenset())
