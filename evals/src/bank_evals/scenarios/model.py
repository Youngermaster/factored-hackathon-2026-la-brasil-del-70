"""The evaluation scenario, version 1 (``contracts/schemas/scenario.v1.json``), minor version 1.1.

One contract shared by the scenario generators, the fixtures, the simulated user, and the graders (phase 14).
Scenarios reference seeded demo personas and their records by symbolic names (for example
``recent_card_purchase``), never by real identifiers, and every scenario states its provenance and review
status. Phase 14 may add fields, additively.

Version 1.1.0 adds the workflow a scenario exercises (``None`` for out-of-scope requests), the expected
workflow path for routing scenarios, the expected eligibility outcome, credit fixtures, credit state
assertions, and disclosure kinds for balances, eligibility, and credit data. New top-level fields are marked
``AddedIn``. Phase 14 adds a generator lint that requires ``workflow`` on in-scope scenarios; the contract
keeps it optional.
"""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveInt,
    StrictInt,
    StringConstraints,
    model_validator,
)

from bank_agent.domain.actions import ToolFailureMode, ToolName
from bank_agent.domain.base import AddedIn, check_added_fields
from bank_agent.domain.credit import ApplicationStatus
from bank_agent.domain.dispute import DisputeReason, DisputeStatus
from bank_agent.domain.eligibility import EligibilityOutcome
from bank_agent.domain.handoff import EscalationReasonCode, Handoff
from bank_agent.domain.identifiers import CreditProductCode
from bank_agent.domain.intelligence import ModelComponent
from bank_agent.domain.locale import Language, Locale
from bank_agent.domain.money import Money
from bank_agent.domain.product import ProductStatus
from bank_agent.domain.workflow import Outcome, WorkflowId

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
    when_asked: Annotated[bool, AddedIn("1.4.0")] = False
    """An answer the customer gives only when the previous reply asked something (a clarifying question or a
    pending step); the driver skips it when the system already finished the request."""

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


class CreditProfileOverride(ScenarioModel):
    """Sets one credit fact of the persona's profile, or clears it with ``value: null`` (missing data)."""

    kind: Literal["credit_profile_override"] = "credit_profile_override"
    fact: Literal["credit_score", "estimated_monthly_income", "max_days_past_due"]
    value: StrictInt | Money | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.value is None:
            return self
        if self.fact == "estimated_monthly_income":
            if not isinstance(self.value, Money) or self.value.amount < 0:
                raise ValueError("estimated_monthly_income takes a non-negative money value")
        elif not isinstance(self.value, int):
            raise ValueError(f"{self.fact} takes an integer")
        elif self.fact == "credit_score" and not 300 <= self.value <= 850:
            raise ValueError("credit_score is between 300 and 850")
        elif self.value < 0:
            raise ValueError("max_days_past_due cannot be negative")
        return self


class ExistingCreditApplication(ScenarioModel):
    kind: Literal["existing_credit_application"] = "existing_credit_application"
    product_code: CreditProductCode
    status: ApplicationStatus = ApplicationStatus.SUBMITTED


class ModelUnavailable(ScenarioModel):
    """The named component fails for the whole scenario, for example the risk estimator."""

    kind: Literal["model_unavailable"] = "model_unavailable"
    component: ModelComponent


Fixture = Annotated[
    MerchantNameOverride
    | ProductStatusOverride
    | ExistingCase
    | SessionExpiresBeforeTurn
    | CreditProfileOverride
    | ExistingCreditApplication
    | ModelUnavailable,
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


class CreditApplicationExists(ScenarioModel):
    kind: Literal["credit_application_exists"] = "credit_application_exists"
    product_code: CreditProductCode | None = None
    status: ApplicationStatus | None = None


class CreditApplicationCount(ScenarioModel):
    kind: Literal["credit_application_count"] = "credit_application_count"
    count: NonNegativeInt


class EligibilityOutcomeIs(ScenarioModel):
    kind: Literal["eligibility_outcome"] = "eligibility_outcome"
    outcome: EligibilityOutcome


StateAssertion = Annotated[
    CaseExists
    | CaseCount
    | ProductStatusIs
    | HandoffExists
    | NoWrites
    | CreditApplicationExists
    | CreditApplicationCount
    | EligibilityOutcomeIs,
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
    BALANCE = "balance"
    AS_OF_DATE = "as_of_date"
    ELIGIBILITY_REASON = "eligibility_reason"
    REVIEW_PATH = "review_path"
    CREDIT_APPROVAL_CLAIM = "credit_approval_claim"
    """A response that states or implies credit approval: always a forbidden disclosure."""
    RISK_ESTIMATE = "risk_estimate"
    CREDIT_SCORE = "credit_score"
    INCOME = "income"


class DisclosureSpec(ScenarioModel):
    kind: DisclosureKind
    value: Annotated[str, StringConstraints(min_length=1, max_length=200)] | None = None


ExpectedOutcome = Literal[Outcome.RESOLVED, Outcome.CLARIFIED, Outcome.ABSTAINED, Outcome.ESCALATED, Outcome.REFUSED]
HANDOFF_FIELDS = frozenset(Handoff.model_fields)


class Scenario(ScenarioModel):
    schema_version: Annotated[str, StringConstraints(pattern=r"^1\.[0-9]+\.[0-9]+$")] = "1.4.0"
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
    workflow: Annotated[WorkflowId | None, AddedIn("1.1.0")] = None
    """The workflow the scenario exercises; ``None`` for out-of-scope requests."""
    expected_workflow_path: Annotated[tuple[WorkflowId, ...], AddedIn("1.1.0")] = ()
    """For routing scenarios: the workflows the conversation visits, in order, starting with ``workflow``."""
    expected_eligibility_outcome: Annotated[EligibilityOutcome | None, AddedIn("1.1.0")] = None
    scripted_fallback: Annotated[tuple[ScriptedTurn, ...], AddedIn("1.4.0")] = ()
    """For a simulated scenario: the turns played when a run has no simulator model (offline and CI runs)."""
    template_family: Annotated[
        Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_.-]{2,63}$")] | None, AddedIn("1.4.0")
    ] = None
    """The generator's template family; a family belongs wholly to one split (leakage guard)."""

    @model_validator(mode="after")
    def _validate(self) -> Self:
        self._validate_language()
        self._validate_mode()
        self._validate_consistency()
        self._validate_workflows()
        return self

    def _validate_workflows(self) -> None:
        check_added_fields(self, self.schema_version)
        if self.workflow is not None and not self.in_scope:
            raise ValueError("an out-of-scope scenario has no workflow")
        if self.expected_workflow_path and (
            len(self.expected_workflow_path) < 2 or self.expected_workflow_path[0] is not self.workflow
        ):
            raise ValueError("a workflow path has at least two workflows and starts with the scenario workflow")
        if self.expected_eligibility_outcome is not None and self.workflow is not WorkflowId.CREDIT:
            raise ValueError("an expected eligibility outcome belongs to a credit scenario")

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
        if self.scripted_fallback and self.mode is not ScenarioMode.SIMULATED:
            raise ValueError("only a simulated scenario has scripted fallback turns")

    def _validate_consistency(self) -> None:
        if set(self.known_facts) & set(self.hidden_facts):
            raise ValueError("a fact is either known or hidden, not both")
        unknown = set(self.expected_handoff_fields) - HANDOFF_FIELDS
        if unknown:
            raise ValueError(f"unknown handoff fields: {sorted(unknown)}")
        if self.expected_handoff_fields and self.expected_outcome is not Outcome.ESCALATED:
            raise ValueError("expected handoff fields need an escalated outcome")
        unavailable = any(isinstance(f, ModelUnavailable) for f in self.fixtures)
        if self.category is ScenarioCategory.TOOL_FAILURE and not (self.tool_failure_plan or unavailable):
            raise ValueError("a tool_failure scenario needs a tool failure plan or an unavailable model")
        expiring = [f for f in self.fixtures if isinstance(f, SessionExpiresBeforeTurn)]
        if self.mode is ScenarioMode.SCRIPTED and any(f.turn_index > len(self.turns) for f in expiring):
            raise ValueError("a session expiry fixture points past the last turn")
        clock_moves = any(turn.advance_clock_seconds > 0 for turn in self.turns)
        if self.category is ScenarioCategory.EXPIRED_SESSION and not (expiring or clock_moves):
            raise ValueError("an expired_session scenario needs a session expiry fixture or a clock advance")
