"""Conversation requests and responses: the turn API for all four workflows.

``AssistantMessage`` carries every part a turn can return: the text, citations (``clause_id@version`` with the
rendered excerpt), clarification options, one confirmation card (dispute, card action, or credit intake), action
statuses with their verification evidence, the escalation reference, the step-up request, notices, and the
workflow parts from phase 02b: balances with their as-of instant, payment statuses, a statement summary, card
status, credit product views, and the customer-facing eligibility view. It never carries a credit profile value or
a risk estimate.

Since the Tuesday MVP contract (ADR 0025), a message can carry the labeled simulated agent's reply after a handoff,
and ``TurnResponse`` carries the request's ``correlation_id`` and, when the turn changed it, the assistant profile.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints

from bank_agent.api.schemas.base import RequestModel, ResponseModel
from bank_agent.api.schemas.profile import AssistantProfileView
from bank_agent.domain.accounts import BalanceView, PaymentStatusView, StatementSummary
from bank_agent.domain.cards import CardStatusView
from bank_agent.domain.conversation import (
    MAX_CUSTOMER_MESSAGE_LENGTH,
    ActionStatusView,
    CardActionConfirmation,
    Citation,
    Clarification,
    ConfirmationCard,
    ConversationStatus,
    CreditIntakeConfirmation,
    EscalationNotice,
    NoticeCode,
    SimulatedAgentReply,
)
from bank_agent.domain.credit import CreditProduct
from bank_agent.domain.eligibility import EligibilityView
from bank_agent.domain.identifiers import ConversationId, CorrelationId, TurnId
from bank_agent.domain.locale import Language
from bank_agent.domain.workflow import Outcome, StateName, WorkflowRef

MessageText = Annotated[str, StringConstraints(min_length=1, max_length=MAX_CUSTOMER_MESSAGE_LENGTH)]


class SendTurnRequest(RequestModel):
    """One customer message. ``turn_id`` is a client-made UUID; sending the same one again replays the result."""

    turn_id: UUID
    text: MessageText


class AssistantMessage(ResponseModel):
    language: Language
    text: str
    template_id: str | None = None
    citations: tuple[Citation, ...] = ()
    clarification: Clarification | None = None
    confirmation: ConfirmationCard | None = None
    card_action_confirmation: CardActionConfirmation | None = None
    credit_intake_confirmation: CreditIntakeConfirmation | None = None
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
    simulated_agent: SimulatedAgentReply | None = Field(
        default=None,
        description="The simulated service agent's reply after a handoff; always labeled simulated (ADR 0025).",
    )


class TurnResponse(ResponseModel):
    """The result of one turn: the assistant message and where the conversation now is."""

    turn_id: TurnId
    conversation_id: ConversationId
    workflow: WorkflowRef | None = Field(description="The workflow after the turn; the router is `router@1`.")
    state: StateName
    outcome: Outcome
    replayed: bool
    message: AssistantMessage
    correlation_id: CorrelationId = Field(
        description="The request id (`X-Request-ID`) that links this turn to its logs, records, and model traces."
    )
    assistant_profile: AssistantProfileView | None = Field(
        default=None, description="The assistant profile after this turn, present only when the turn changed it."
    )


class ConversationView(ResponseModel):
    conversation_id: ConversationId
    status: ConversationStatus
    language: Language | None
    workflow: WorkflowRef
    state: StateName
    created_at: datetime
    updated_at: datetime


class TurnView(ResponseModel):
    turn_id: TurnId
    sequence: int
    received_at: datetime
    customer_text: str
    language: Language | None
    message: AssistantMessage | None
    completed_at: datetime | None


class ConversationHistoryResponse(ResponseModel):
    conversation: ConversationView
    turns: tuple[TurnView, ...]
