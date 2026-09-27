"""What the engine keeps between turns inside ``WorkflowPosition.data`` (JSON), typed.

``data["engine"]`` holds engine state shared by every workflow: the conversation-wide turn counter, pending
questions (language, workflow choice, a switch), the resume state after a session expiry, the executed writes
keyed by idempotency key (so a resumed step never writes twice), the verified facts collected so far, and the
handoff id once the conversation is escalated. ``data["flow"]`` holds the current workflow's own model.
"""

from datetime import date
from typing import Annotated

from pydantic import Field, JsonValue, NonNegativeInt

from bank_agent.domain.actions import ActionKind
from bank_agent.domain.base import Code, DomainModel, SingleLineText
from bank_agent.domain.handoff import MAX_VERIFIED_FACTS
from bank_agent.domain.identifiers import HandoffId, IdempotencyKey, SourceRef
from bank_agent.domain.workflow import Intent, WorkflowId

ENGINE_KEY = "engine"
FLOW_KEY = "flow"
MAX_PENDING_TEXT = 2000


class PendingSwitch(DomainModel):
    target: WorkflowId
    intent: Intent
    text: Annotated[str, Field(max_length=MAX_PENDING_TEXT)]


class PendingWorkflowChoice(DomainModel):
    options: tuple[WorkflowId, ...]
    text: Annotated[str, Field(max_length=MAX_PENDING_TEXT)]


class ExecutedAction(DomainModel):
    """A write that ran in this conversation, with its read-back result."""

    action: ActionKind
    target: SourceRef
    idempotency_key: IdempotencyKey
    outcome_ref: SourceRef | None = None
    verified: bool = False
    mismatch_code: Code | None = None
    failed: bool = False


class FactEntry(DomainModel):
    fact: SingleLineText
    source: SourceRef


class EngineData(DomainModel):
    sequence: NonNegativeInt = 0
    pending_language_text: Annotated[str, Field(max_length=MAX_PENDING_TEXT)] | None = None
    pending_choice: PendingWorkflowChoice | None = None
    pending_switch: PendingSwitch | None = None
    resume_state: str | None = None
    handoff_id: HandoffId | None = None
    handoff_due: date | None = None
    executed: tuple[ExecutedAction, ...] = ()
    facts: Annotated[tuple[FactEntry, ...], Field(max_length=MAX_VERIFIED_FACTS)] = ()
    intent: Intent | None = None
    """The intent the current workflow is serving, for the kernel when no new prediction applies."""
    carried_card: SourceRef | None = None
    """A card chosen in ``card_support``, carried into ``dispute`` after a switch as a verified fact."""

    def executed_for(self, key: str) -> ExecutedAction | None:
        return next((item for item in self.executed if item.idempotency_key == key), None)

    def with_executed(self, entry: ExecutedAction) -> "EngineData":
        kept = tuple(item for item in self.executed if item.idempotency_key != entry.idempotency_key)
        return self.evolve(executed=(*kept, entry))

    def with_fact(self, fact: str, source: SourceRef) -> "EngineData":
        entry = FactEntry(fact=fact[:300], source=source)
        if entry in self.facts:
            return self
        return self.evolve(facts=(*self.facts, entry)[-MAX_VERIFIED_FACTS:])


def load_engine(data: dict[str, JsonValue]) -> EngineData:
    raw = data.get(ENGINE_KEY)
    return EngineData.model_validate(raw) if isinstance(raw, dict) else EngineData()


def dump(model: DomainModel) -> dict[str, JsonValue]:
    dumped: dict[str, JsonValue] = model.model_dump(mode="json")
    return dumped
