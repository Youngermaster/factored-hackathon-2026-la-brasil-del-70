"""The evaluation scenario, version 1 (``contracts/schemas/scenario.v1.json``).

One contract shared by the scenario generators, the fixtures, the simulated user, and the graders (phase 14).
Scenarios reference seeded demo personas and their records by symbolic names (for example
``recent_card_purchase``), never by real identifiers, and every scenario states its provenance and review
status. Phase 14 may add fields, additively.
"""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, PositiveInt, StringConstraints, model_validator

from bank_agent.domain.actions import ToolFailureMode, ToolName
from bank_agent.domain.dispute import DisputeReason, DisputeStatus
from bank_agent.domain.handoff import EscalationReasonCode, Handoff
from bank_agent.domain.locale import Language, Locale
from bank_agent.domain.product import ProductStatus
from bank_agent.domain.workflow import Outcome

SlotName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
RecordRef = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
"""A symbolic name for a persona's record, resolved by the harness against the seeded data."""
FactText = Annotated[str, StringConstraints(min_length=1, max_length=300)]


class ScenarioModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Split(StrEnum):
    DEV = "dev"
    TEST = "test"


class ScenarioCategory(StrEnum):
    NORMAL = "normal"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"
    HUMAN_REQUIRED = "human_required"
    MISSING_OR_INCORRECT_DATA = "missing_or_incorrect_data"
    EXPIRED_SESSION = "expired_session"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    PROMPT_INJECTION = "prompt_injection"
    TOOL_FAILURE = "tool_failure"


class ScenarioMode(StrEnum):
    SCRIPTED = "scripted"
    SIMULATED = "simulated"


class Provenance(StrEnum):
    DERIVED_FROM_RECORD = "derived_from_record"
    TEAM_GENERATED = "team_generated"
    TRANSLATED = "translated"
    LLM_PARAPHRASE = "llm_paraphrase"


class ReviewStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class TurnAction(StrEnum):
    SELECT_OPTION = "select_option"
    CONFIRM = "confirm"
    DECLINE = "decline"
    COMPLETE_STEP_UP = "complete_step_up"


class ScriptedTurn(ScenarioModel):
    """One customer turn: either a message or an action, optionally after the clock moves forward."""

    text: Annotated[str, StringConstraints(min_length=1, max_length=2000)] | None = None
    action: TurnAction | None = None
    option_index: Annotated[int, Field(ge=1, le=3)] | None = None
    advance_clock_seconds: NonNegativeInt = 0

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if (self.text is None) == (self.action is None):
            raise ValueError("a turn has either text or an action")
        if (self.action is TurnAction.SELECT_OPTION) != (self.option_index is not None):
            raise ValueError("option_index goes with select_option, and only with it")
        return self


class MerchantNameOverride(ScenarioModel):
    """Replaces a record's merchant name, for example with indirect prompt-injection text."""

    kind: Literal["merchant_name_override"] = "merchant_name_override"
    transaction_ref: RecordRef
    value: Annotated[str, StringConstraints(min_length=1, max_length=150)]


class ProductStatusOverride(ScenarioModel):
    kind: Literal["product_status_override"] = "product_status_override"
    product_ref: RecordRef
    status: ProductStatus


class ExistingCase(ScenarioModel):
    kind: Literal["existing_case"] = "existing_case"
    transaction_ref: RecordRef
    status: DisputeStatus
    reason: DisputeReason


class SessionExpiresBeforeTurn(ScenarioModel):
    kind: Literal["session_expires_before_turn"] = "session_expires_before_turn"
    turn_index: PositiveInt


Fixture = Annotated[
    MerchantNameOverride | ProductStatusOverride | ExistingCase | SessionExpiresBeforeTurn,
    Field(discriminator="kind"),
]


class ToolFailureStep(ScenarioModel):
    """Fail the ``on_call``-th call of ``tool`` (1-based), ``times`` times in a row."""

    tool: ToolName
    mode: ToolFailureMode
    on_call: PositiveInt = 1
    times: PositiveInt = 1


class CaseExists(ScenarioModel):
    kind: Literal["case_exists"] = "case_exists"
    transaction_ref: RecordRef
    reason: DisputeReason | None = None
    status: DisputeStatus | None = None


class CaseCount(ScenarioModel):
    kind: Literal["case_count"] = "case_count"
    count: NonNegativeInt


class ProductStatusIs(ScenarioModel):
    kind: Literal["product_status"] = "product_status"
    product_ref: RecordRef
    status: ProductStatus


class HandoffExists(ScenarioModel):
    kind: Literal["handoff_exists"] = "handoff_exists"
    reason_code: EscalationReasonCode | None = None


class NoWrites(ScenarioModel):
    kind: Literal["no_writes"] = "no_writes"


StateAssertion = Annotated[
    CaseExists | CaseCount | ProductStatusIs | HandoffExists | NoWrites,
    Field(discriminator="kind"),
]


class DisclosureKind(StrEnum):
    CASE_REFERENCE = "case_reference"
    SLA = "sla"
    CLAUSE_CITATION = "clause_citation"
    OTHER_CUSTOMER_ID = "other_customer_id"
    OTHER_CUSTOMER_NAME = "other_customer_name"
    PRODUCT_NUMBER = "product_number"
    INTERNAL_FLAG = "internal_flag"
    FRAUD_SCORE = "fraud_score"
    PHRASE = "phrase"


class DisclosureSpec(ScenarioModel):
    kind: DisclosureKind
    value: Annotated[str, StringConstraints(min_length=1, max_length=200)] | None = None


ExpectedOutcome = Literal[Outcome.RESOLVED, Outcome.CLARIFIED, Outcome.ABSTAINED, Outcome.ESCALATED, Outcome.REFUSED]
HANDOFF_FIELDS = frozenset(Handoff.model_fields)


class Scenario(ScenarioModel):
    schema_version: Annotated[str, StringConstraints(pattern=r"^1\.[0-9]+\.[0-9]+$")] = "1.0.0"
    id: Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]{2,63}$")]
    split: Split
    language: Language
    dialect: Locale
    category: ScenarioCategory
    tags: tuple[SlotName, ...] = ()
    persona_ref: Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")]
    goal: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    known_facts: dict[SlotName, FactText] = Field(default_factory=dict)
    hidden_facts: dict[SlotName, FactText] = Field(default_factory=dict)
    """Revealed by the simulated user only when asked."""
    mode: ScenarioMode
    turns: tuple[ScriptedTurn, ...] = ()
    simulator_instructions: Annotated[str, StringConstraints(min_length=1, max_length=2000)] | None = None
    fixtures: tuple[Fixture, ...] = ()
    tool_failure_plan: tuple[ToolFailureStep, ...] = ()
    expected_outcome: ExpectedOutcome
    expected_state_assertions: tuple[StateAssertion, ...] = ()
    required_disclosures: tuple[DisclosureSpec, ...] = ()
    forbidden_disclosures: tuple[DisclosureSpec, ...] = ()
    expected_handoff_fields: tuple[str, ...] = ()
    in_scope: bool
    provenance: Provenance
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW

    @model_validator(mode="after")
    def _validate(self) -> Self:
        self._validate_language()
        self._validate_mode()
        self._validate_consistency()
        return self

    def _validate_language(self) -> None:
        if self.language is Language.EN:
            raise ValueError("customer scenarios are in Spanish or Portuguese")
        if self.dialect.language is not self.language:
            raise ValueError("the dialect must belong to the scenario language")

    def _validate_mode(self) -> None:
        if self.mode is ScenarioMode.SCRIPTED and (not self.turns or self.simulator_instructions is not None):
            raise ValueError("a scripted scenario has turns and no simulator instructions")
        if self.mode is ScenarioMode.SIMULATED and (self.turns or self.simulator_instructions is None):
            raise ValueError("a simulated scenario has simulator instructions and no scripted turns")

    def _validate_consistency(self) -> None:
        if set(self.known_facts) & set(self.hidden_facts):
            raise ValueError("a fact is either known or hidden, not both")
        unknown = set(self.expected_handoff_fields) - HANDOFF_FIELDS
        if unknown:
            raise ValueError(f"unknown handoff fields: {sorted(unknown)}")
        if self.expected_handoff_fields and self.expected_outcome is not Outcome.ESCALATED:
            raise ValueError("expected handoff fields need an escalated outcome")
        if self.category is ScenarioCategory.TOOL_FAILURE and not self.tool_failure_plan:
            raise ValueError("a tool_failure scenario needs a tool failure plan")
        expiring = [f for f in self.fixtures if isinstance(f, SessionExpiresBeforeTurn)]
        if self.mode is ScenarioMode.SCRIPTED and any(f.turn_index > len(self.turns) for f in expiring):
            raise ValueError("a session expiry fixture points past the last turn")
        clock_moves = any(turn.advance_clock_seconds > 0 for turn in self.turns)
        if self.category is ScenarioCategory.EXPIRED_SESSION and not (expiring or clock_moves):
            raise ValueError("an expired_session scenario needs a session expiry fixture or a clock advance")
