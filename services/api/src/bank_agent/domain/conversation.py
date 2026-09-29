"""Conversations, turns, and what the assistant returns for a turn.

Turns are stored for the conversation history and never copied into a handoff. ``AssistantResponse`` covers
every message variant the chat renders (phase 13): plain text, citations, clarification options, the
confirmation cards (dispute, card action, credit intake; at most one per response), action statuses, the
escalation notice, a step-up request, system notices, and the account, card, and credit views. All text is
rendered as plain text.
"""

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, JsonValue, NonNegativeInt, PositiveInt, StringConstraints, model_validator

from bank_agent.domain.access import Channel
from bank_agent.domain.accounts import BalanceView, PaymentStatusView, StatementSummary
from bank_agent.domain.actions import ActionKind
from bank_agent.domain.base import Code, DisplayText, DomainModel, Pii, UntrustedText, UtcDatetime
from bank_agent.domain.cards import SELF_SERVICE_CARD_ACTIONS, CardAction, CardBlockReason, CardStatusView
from bank_agent.domain.credit import CreditProduct, CreditProductType, TermMonths
from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.dispute import DisputeReason
from bank_agent.domain.eligibility import (
    INDICATIVE_DISCLAIMER,
    EligibilityOutcome,
    EligibilityView,
    IndicativeDisclaimer,
)
from bank_agent.domain.identifiers import (
    ConversationId,
    CreditProductCode,
    CustomerId,
    HandoffId,
    LineageId,
    SourceRef,
    TurnId,
)
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.money import Money
from bank_agent.domain.workflow import Outcome, StateName, WorkflowRef

MAX_CUSTOMER_MESSAGE_LENGTH = 2000
TemplateId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_.]{0,127}$")]
Last4 = Annotated[str, StringConstraints(pattern=r"^[0-9A-Z]{4}$")]


class ConversationStatus(StrEnum):
    ACTIVE = "active"
    ESCALATED = "escalated"
    CLOSED = "closed"


class WorkflowPosition(DomainModel):
    """Where a conversation is in its workflow. ``data`` is opaque here and typed per workflow in phase 09."""

    workflow: WorkflowRef
    state: StateName
    clarifications_used: NonNegativeInt = 0
    turns_used: NonNegativeInt = 0
    data: dict[str, JsonValue] = Field(default_factory=dict)


class Conversation(DomainModel):
    conversation_id: ConversationId
    customer_id: CustomerId
    lineage_id: LineageId
    channel: Channel
    jurisdiction: Country
    language: Language | None = None
    status: ConversationStatus = ConversationStatus.ACTIVE
    position: WorkflowPosition
    created_at: UtcDatetime
    updated_at: UtcDatetime
    version: NonNegativeInt = 0
    """Optimistic concurrency: repositories reject an update whose expected version is stale."""

    @model_validator(mode="after")
    def _validate_times(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        return self


class Citation(DomainModel):
    clause: ClauseRef
    excerpt: Annotated[str, StringConstraints(min_length=1, max_length=1000)]


class ClarificationOption(DomainModel):
    """One candidate transaction, shown masked. The option id is opaque; the transaction id stays server side."""

    option_id: Annotated[str, StringConstraints(pattern=r"^opt-[0-9]{1,2}$")]
    occurred_on: date
    merchant_display: DisplayText | None = None
    amount: Money
    card_last4: Last4 | None = None


class Clarification(DomainModel):
    options: Annotated[tuple[ClarificationOption, ...], Field(max_length=3)] = ()


class ConfirmationCard(DomainModel):
    occurred_on: date
    merchant_display: DisplayText | None = None
    amount: Money
    card_last4: Last4 | None = None
    reason: DisputeReason
    planned_actions: Annotated[tuple[ActionKind, ...], Field(min_length=1)]
    expected_resolution_by: date | None = None


class CardActionConfirmation(DomainModel):
    """What the customer confirms before a card write. Only self-service card actions have one."""

    action: CardAction
    card_last4: Last4
    reason: CardBlockReason | None = None
    planned_actions: Annotated[tuple[ActionKind, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.action not in SELF_SERVICE_CARD_ACTIONS:
            raise ValueError("only a self-service card action is confirmed; the others go to a human")
        if ActionKind.BLOCK_CARD not in self.planned_actions:
            raise ValueError("a card block confirmation plans the block_card action")
        return self


class CreditIntakeConfirmation(DomainModel):
    """What the customer confirms before an application intake is recorded for human review.

    It shows no declared income, and states that the result is indicative, not an offer or a decision.
    """

    product_code: CreditProductCode
    product_type: CreditProductType
    requested_amount: Money
    requested_term_months: TermMonths
    purpose: Code
    eligibility_outcome: EligibilityOutcome | None = None
    disclaimer: IndicativeDisclaimer = INDICATIVE_DISCLAIMER
    planned_actions: Annotated[tuple[ActionKind, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if ActionKind.SUBMIT_CREDIT_APPLICATION not in self.planned_actions:
            raise ValueError("an intake confirmation plans the submit_credit_application action")
        return self


class ActionDisplayStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


class ActionStatusView(DomainModel):
    action: ActionKind
    status: ActionDisplayStatus
    reference: SourceRef | None = None
    evidence: SourceRef | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.status is ActionDisplayStatus.VERIFIED and self.evidence is None:
            raise ValueError("an action can be shown as verified only with evidence")
        return self


class EscalationNotice(DomainModel):
    handoff_id: HandoffId
    expected_response_by: UtcDatetime


class SimulatedAgentReply(DomainModel):
    """A reply from the simulated human service agent that joins the chat after a handoff (ADR 0025).

    ``simulated`` is always true and the chat labels it: no person joined, read, or acted on the conversation.
    The text comes from a bounded, reviewed template list and never promises an outcome.
    """

    agent_display_name: Annotated[str, StringConstraints(min_length=1, max_length=60)]
    text: Annotated[str, StringConstraints(min_length=1, max_length=1000)]
    joined_at: UtcDatetime
    simulated: Literal[True] = True


class NoticeCode(StrEnum):
    SESSION_EXPIRED = "session_expired"
    REAUTHENTICATION_REQUIRED = "reauthentication_required"
    LANGUAGE_QUESTION = "language_question"


class AssistantResponse(DomainModel):
    language: Language
    text: Annotated[str, StringConstraints(max_length=4000)]
    template_id: TemplateId | None = None
    citations: tuple[Citation, ...] = ()
    clarification: Clarification | None = None
    confirmation: ConfirmationCard | None = None
    action_statuses: tuple[ActionStatusView, ...] = ()
    escalation: EscalationNotice | None = None
    step_up_required: bool = False
    notices: tuple[NoticeCode, ...] = ()
    balances: tuple[BalanceView, ...] = ()
    payment_statuses: tuple[PaymentStatusView, ...] = ()
    statement: StatementSummary | None = None
    card_status: tuple[CardStatusView, ...] = ()
    credit_products: tuple[CreditProduct, ...] = ()
    eligibility: EligibilityView | None = None
    card_action_confirmation: CardActionConfirmation | None = None
    credit_intake_confirmation: CreditIntakeConfirmation | None = None
    simulated_agent: SimulatedAgentReply | None = None

    @model_validator(mode="after")
    def _validate_confirmations(self) -> Self:
        confirmations = (self.confirmation, self.card_action_confirmation, self.credit_intake_confirmation)
        if sum(item is not None for item in confirmations) > 1:
            raise ValueError("a response asks for at most one confirmation")
        if self.simulated_agent is not None and self.escalation is None:
            raise ValueError("a simulated agent joins only a conversation that was handed off")
        return self


class Turn(DomainModel):
    turn_id: TurnId
    conversation_id: ConversationId
    sequence: PositiveInt
    received_at: UtcDatetime
    customer_text: Annotated[
        UntrustedText, StringConstraints(min_length=1, max_length=MAX_CUSTOMER_MESSAGE_LENGTH), Pii("free_text")
    ]
    language: Language | None = None
    response: AssistantResponse | None = None
    completed_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if (self.response is None) != (self.completed_at is None):
            raise ValueError("a completed turn has both a response and a completion time")
        if self.completed_at is not None and self.completed_at < self.received_at:
            raise ValueError("a turn cannot complete before it was received")
        return self


class TurnResult(DomainModel):
    """What processing one turn returns (phase 09) and what the API maps to its response (phase 11)."""

    turn_id: TurnId
    conversation_id: ConversationId
    state: StateName
    outcome: Outcome
    response: AssistantResponse
    workflow: WorkflowRef | None = None
    """The workflow (or the router) the conversation is in after the turn, from the turn's execution record."""
    replayed: bool = False
    """True when the turn id was already processed and the stored result is returned again."""
