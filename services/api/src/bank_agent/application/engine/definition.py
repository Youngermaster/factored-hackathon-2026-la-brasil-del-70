"""Workflow definitions as data: states, allowed transitions, a handler per state, tools, and bound clauses.

A ``StateSpec`` names the canonical binding state it is evaluated and grounded in (``policy_state``), so the clauses
bound to an engine state come from ``policies/bindings.yaml`` and are never repeated in code. ``build_definition``
adds the shared exits (ESCALATED, ABSTAINED, REFUSED, AUTH_REQUIRED) to every non-terminal state, and lets
AUTH_REQUIRED resume to any non-terminal state, so the transition table is complete and explicit. Any move that is
not in the table raises ``WorkflowTransitionError``.
"""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from bank_agent.domain.actions import ActionKind, ToolName
from bank_agent.domain.errors import WorkflowTransitionError
from bank_agent.domain.workflow import Intent, WorkflowId, WorkflowRef

if TYPE_CHECKING:
    from bank_agent.application.engine.context import Step, TurnContext

ESCALATED = "ESCALATED"
ABSTAINED = "ABSTAINED"
REFUSED = "REFUSED"
AUTH_REQUIRED = "AUTH_REQUIRED"
RESOLVED = "RESOLVED"
START = "START"
SHARED_EXITS = frozenset({ESCALATED, ABSTAINED, REFUSED, AUTH_REQUIRED})


class StateKind(StrEnum):
    ACCEPTS_REQUEST = "accepts_request"
    """The router runs before the handler: a new request may start or switch a workflow."""
    AWAITS_ANSWER = "awaits_answer"
    """The handler parses an expected answer first; when it does not parse, the router may offer a switch."""
    WORKING = "working"
    """Reached only within a turn (no customer input is expected here)."""
    TERMINAL = "terminal"


Handler = Callable[["TurnContext"], Awaitable["Step"]]


@dataclass(frozen=True)
class StateSpec:
    name: str
    policy_state: str
    handler: Handler
    kind: StateKind
    allowed_tools: frozenset[ToolName] = frozenset()
    action_policy_states: Mapping[ActionKind, str] = field(default_factory=dict)
    """For states that write: the binding state each write action is evaluated in (``CREATE_CASE``...)."""
    resume_state: str | None = None
    """Where a session expiry in this state resumes after re-authentication (the last safe state)."""
    holds_context: bool = False
    """An accepting state that still holds the customer's context (a card just shown); a switch is confirmed."""

    @property
    def mid_flow(self) -> bool:
        """A request for another workflow here must be confirmed before the pending work is left."""
        return self.holds_context or self.kind in (StateKind.AWAITS_ANSWER, StateKind.WORKING)


@dataclass(frozen=True)
class WorkflowDefinition:
    workflow: WorkflowId
    version: int
    entry_state: str
    states: Mapping[str, StateSpec]
    transitions: Mapping[str, frozenset[str]]
    intents: frozenset[Intent]
    variant: str = "proposed"
    open_questions: Callable[["TurnContext"], tuple[str, ...]] | None = None
    """Questions a handoff lists from the workflow's unresolved slots, whichever step escalates."""

    def __post_init__(self) -> None:
        if self.entry_state not in self.states:
            raise WorkflowTransitionError(f"entry state {self.entry_state} is not a state of {self.workflow}")
        for name, spec in self.states.items():
            if spec.name != name:
                raise WorkflowTransitionError(f"state {name} is registered under another name")
            if spec.resume_state is not None and spec.resume_state not in self.states:
                raise WorkflowTransitionError(f"state {name} resumes to unknown state {spec.resume_state}")
        for source, targets in self.transitions.items():
            unknown = sorted((targets | {source}) - set(self.states))
            if unknown:
                raise WorkflowTransitionError(f"transitions of {self.workflow} name unknown states {unknown}")
            if self.states[source].kind is StateKind.TERMINAL and targets:
                raise WorkflowTransitionError(f"terminal state {source} cannot have exits")

    @property
    def ref(self) -> WorkflowRef:
        return WorkflowRef(id=self.workflow.value, version=self.version)

    def spec(self, state: str) -> StateSpec:
        try:
            return self.states[state]
        except KeyError:
            raise WorkflowTransitionError(f"{state} is not a state of {self.workflow}") from None

    def allows(self, source: str, target: str) -> bool:
        return source == target or target in self.transitions.get(source, frozenset())

    def check_transition(self, source: str, target: str) -> None:
        """Raise ``WorkflowTransitionError`` unless ``source`` may move to ``target`` (staying is always allowed)."""
        self.spec(source)
        self.spec(target)
        if not self.allows(source, target):
            raise WorkflowTransitionError(f"{self.workflow} cannot move from {source} to {target}")


def build_definition(
    *,
    workflow: WorkflowId,
    version: int,
    states: tuple[StateSpec, ...],
    transitions: Mapping[str, tuple[str, ...]],
    intents: frozenset[Intent],
    entry_state: str = START,
    variant: str = "proposed",
    open_questions: Callable[["TurnContext"], tuple[str, ...]] | None = None,
) -> WorkflowDefinition:
    """A definition whose table also holds the shared exits and the AUTH_REQUIRED resumes."""
    by_name = {spec.name: spec for spec in states}
    open_states = {name for name, spec in by_name.items() if spec.kind is not StateKind.TERMINAL}
    table: dict[str, frozenset[str]] = {}
    for name, spec in by_name.items():
        targets = set(transitions.get(name, ()))
        if spec.kind is not StateKind.TERMINAL:
            targets |= SHARED_EXITS & set(by_name)
        if name == AUTH_REQUIRED:
            targets |= open_states
        targets.discard(name)
        table[name] = frozenset(targets)
    return WorkflowDefinition(
        workflow=workflow,
        version=version,
        entry_state=entry_state,
        states=by_name,
        transitions=table,
        intents=intents,
        variant=variant,
        open_questions=open_questions,
    )
