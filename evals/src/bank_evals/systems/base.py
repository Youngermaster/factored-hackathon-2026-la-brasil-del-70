"""The common interface of the systems under test and the normalized transcript every grader reads.

A system starts one case from a scenario and a fresh copy of the evaluation world (``start``), then the user
driver sends customer turns and session events to the case (``CaseSession``). Whatever the system, the case ends
as a ``Transcript``: turns with their observed outcomes, tool calls, model calls, and structured parts, the
handoffs it created, and the end state of the world it wrote to. Graders never talk to a system directly.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from bank_evals.scenarios.model import Scenario
from bank_evals.world.model import World


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolCallView(Record):
    tool: str
    status: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    verified: bool | None = None
    """The read-back result for a write (``None`` when no verification ran)."""
    customer_id: str | None = None
    """The customer the call read or wrote (B1 passes it as an argument; P and B0 use the session's)."""


class LlmCallView(Record):
    prompt: str
    model: str
    status: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal = Decimal(0)
    latency_ms: int = 0
    role: str = "system"
    """``system`` (the system under test), ``user`` (the simulated customer), or ``judge``."""


class TurnView(Record):
    index: int
    customer_text: str
    assistant_text: str
    outcome: str
    """resolved, clarified, abstained, escalated, refused, or in_progress."""
    state: str | None = None
    workflow: str | None = None
    workflow_before: str | None = None
    language: str | None = None
    template_id: str | None = None
    latency_ms: int = 0
    tool_calls: list[ToolCallView] = Field(default_factory=list)
    llm_calls: list[LlmCallView] = Field(default_factory=list)
    step_up_required: bool = False
    notices: list[str] = Field(default_factory=list)
    handoff_id: str | None = None
    verified_actions: list[str] = Field(default_factory=list)
    """Actions shown to the customer as verified (with evidence)."""
    claimed_actions: list[str] = Field(default_factory=list)
    """Actions the reply says were done (P and B0: action statuses; B1: its declared actions)."""
    eligibility_outcome: str | None = None
    balances: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    safety_interventions: list[str] = Field(default_factory=list)
    driver: str = "scripted"


class EndState(Record):
    product_statuses: dict[str, str] = Field(default_factory=dict)
    cases: list[dict[str, Any]] = Field(default_factory=list)
    """New and existing cases: ``case_id``, ``transaction_id``, ``customer_id``, ``reason``, ``status``."""
    applications: list[dict[str, Any]] = Field(default_factory=list)
    handoffs: list[dict[str, Any]] = Field(default_factory=list)
    """Each handoff as a JSON document (``schema_valid`` says whether it validates against ``handoff.v1.json``)."""
    writes: int = 0
    """Writes the case performed (new cases, blocked cards, submitted applications)."""


class Transcript(Record):
    scenario_id: str
    system: str
    run_index: int = 1
    model_label: str
    turns: list[TurnView] = Field(default_factory=list)
    end_state: EndState = Field(default_factory=EndState)
    error: str | None = None
    """A harness error (the case could not be played); such cases are excluded from metrics and counted."""
    cassette_misses: int = 0

    @property
    def workflow_path(self) -> list[str]:
        path: list[str] = []
        for turn in self.turns:
            if turn.workflow and turn.workflow != "router" and (not path or path[-1] != turn.workflow):
                path.append(turn.workflow)
        return path


class CaseSession(Protocol):
    """One conversation of one case."""

    async def send(self, text: str) -> TurnView:
        """Send a customer message and return the system's turn."""
        ...

    async def reauthenticate(self) -> None:
        """Sign the customer in again after an expired session."""
        ...

    async def step_up(self) -> None:
        """Complete step-up authentication (a new one-time code)."""
        ...

    def expire_session(self) -> None:
        """Make the current session expire before the next turn."""
        ...

    def advance_clock(self, seconds: int) -> None: ...

    async def finish(self) -> EndState:
        """The end state of the world this case wrote to."""
        ...


class SystemUnderTest(Protocol):
    name: str
    """The published system id: ``p``, ``b0``, or ``b1``."""

    @property
    def model_label(self) -> str:
        """The model and provider behind the system's language model paths, or ``none``."""
        ...

    async def start(self, scenario: Scenario, world: World, *, run_index: int) -> CaseSession: ...
