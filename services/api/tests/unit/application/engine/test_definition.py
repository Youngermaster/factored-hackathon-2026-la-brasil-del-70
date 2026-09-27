"""Definitions as data: the builder adds the shared exits, and every move outside the table raises."""

import pytest

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.definition import (
    AUTH_REQUIRED,
    ESCALATED,
    SHARED_EXITS,
    StateKind,
    StateSpec,
    WorkflowDefinition,
    build_definition,
)
from bank_agent.domain.errors import WorkflowTransitionError
from bank_agent.domain.workflow import Intent, WorkflowId


async def noop(ctx: TurnContext) -> Step:
    return Step(ctx.state)


def spec(name: str, kind: StateKind = StateKind.WORKING, **extra: object) -> StateSpec:
    return StateSpec(name=name, policy_state="START", handler=noop, kind=kind, **extra)  # type: ignore[arg-type]


STATES = (
    spec("START", StateKind.ACCEPTS_REQUEST),
    spec("UNDERSTAND"),
    spec("CONFIRM", StateKind.AWAITS_ANSWER, resume_state="CONFIRM"),
    spec("RESOLVED", StateKind.ACCEPTS_REQUEST),
    spec(AUTH_REQUIRED),
    spec(ESCALATED, StateKind.TERMINAL),
    spec("ABSTAINED", StateKind.ACCEPTS_REQUEST),
    spec("REFUSED", StateKind.ACCEPTS_REQUEST),
)


def toy() -> WorkflowDefinition:
    return build_definition(
        workflow=WorkflowId.DISPUTE,
        version=1,
        states=STATES,
        transitions={"START": ("UNDERSTAND",), "UNDERSTAND": ("CONFIRM",), "CONFIRM": ("RESOLVED",)},
        intents=frozenset({Intent.DISPUTE_NEW, Intent.DISPUTE_STATUS}),
    )


def test_every_open_state_gets_the_shared_exits_and_auth_required_resumes_anywhere() -> None:
    definition = toy()
    for name, targets in definition.transitions.items():
        if name == ESCALATED:
            assert targets == frozenset()
        else:
            assert (SHARED_EXITS - {name}) <= targets
    assert {"START", "UNDERSTAND", "CONFIRM", "RESOLVED"} <= definition.transitions[AUTH_REQUIRED]


def test_every_move_outside_the_table_raises() -> None:
    definition = toy()
    allowed = {(source, target) for source, targets in definition.transitions.items() for target in targets}
    for source in definition.states:
        for target in definition.states:
            if source == target or (source, target) in allowed:
                definition.check_transition(source, target)
            else:
                with pytest.raises(WorkflowTransitionError):
                    definition.check_transition(source, target)


def test_unknown_states_and_terminal_exits_are_rejected() -> None:
    definition = toy()
    with pytest.raises(WorkflowTransitionError):
        definition.check_transition("START", "NOWHERE")
    with pytest.raises(WorkflowTransitionError):
        WorkflowDefinition(
            workflow=WorkflowId.DISPUTE,
            version=1,
            entry_state="START",
            states={s.name: s for s in STATES},
            transitions={ESCALATED: frozenset({"START"})},
            intents=frozenset(),
        )
    with pytest.raises(WorkflowTransitionError):
        build_definition(
            workflow=WorkflowId.DISPUTE, version=1, states=STATES, transitions={}, intents=frozenset(), entry_state="X"
        )
    with pytest.raises(WorkflowTransitionError):
        build_definition(
            workflow=WorkflowId.DISPUTE,
            version=1,
            states=(*STATES, spec("BROKEN", resume_state="MISSING")),
            transitions={},
            intents=frozenset(),
        )


def test_mid_flow_follows_the_state_kind() -> None:
    definition = toy()
    assert definition.spec("CONFIRM").mid_flow is True
    assert definition.spec("RESOLVED").mid_flow is False
    assert spec("SHOWN", StateKind.ACCEPTS_REQUEST, holds_context=True).mid_flow is True
    assert definition.ref.id == "dispute"
