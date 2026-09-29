"""Agent console requests and responses: handoffs with their lifecycle, and credit application intakes.

The handoff view is the structured handoff (request summary, verified facts, actions taken, policy basis, open
questions); it never includes a transcript. Agents see the credit review's internal risk estimate (phase 02b rule).
"""

from datetime import datetime
from typing import Annotated

from pydantic import StringConstraints

from bank_agent.api.schemas.base import RequestModel, ResponseModel
from bank_agent.domain.cards import CardRequest
from bank_agent.domain.complaint import Priority
from bank_agent.domain.credit import ApplicationStatus, ApplicationStatusChange
from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.eligibility import CreditReview
from bank_agent.domain.handoff import (
    ActionTaken,
    EscalationReason,
    HandoffAuth,
    HandoffOutcomeCode,
    HandoffRecord,
    HandoffRequest,
    HandoffResolution,
    HandoffStatus,
    Sentiment,
    VerifiedFact,
)
from bank_agent.domain.identifiers import (
    ApplicationId,
    AssessmentId,
    CaseId,
    ConversationId,
    CreditProductCode,
    CustomerId,
    HandoffId,
    StaffId,
)
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.money import Money
from bank_agent.domain.workflow import StateName, WorkflowRef


class HandoffView(ResponseModel):
    handoff_id: HandoffId
    schema_version: str
    created_at: datetime
    status: HandoffStatus
    claimed_by: StaffId | None
    claimed_at: datetime | None
    resolution: HandoffResolution | None
    conversation_ref: ConversationId
    customer_ref: CustomerId
    case_ref: CaseId | None
    workflow: WorkflowRef | None
    state_at_escalation: StateName
    language: Language
    jurisdiction: Country
    auth: HandoffAuth
    request: HandoffRequest
    verified_facts: tuple[VerifiedFact, ...]
    actions_taken: tuple[ActionTaken, ...]
    policy_basis: tuple[ClauseRef, ...]
    escalation_reason: EscalationReason
    open_questions: tuple[str, ...]
    customer_sentiment: Sentiment
    priority: Priority
    sla_due: datetime
    credit_review: CreditReview | None
    card_request: CardRequest | None

    @classmethod
    def of(cls, record: HandoffRecord) -> "HandoffView":
        document = record.handoff
        fields = {name: getattr(document, name) for name in cls.model_fields if hasattr(document, name)}
        fields.update(
            status=record.status,
            claimed_by=record.claimed_by,
            claimed_at=record.claimed_at,
            resolution=record.resolution,
        )
        return cls.model_validate(fields)


class HandoffListResponse(ResponseModel):
    handoffs: tuple[HandoffView, ...]


class ResolveHandoffRequest(RequestModel):
    outcome: HandoffOutcomeCode
    note: Annotated[str, StringConstraints(max_length=500)] = ""


class CreditApplicationView(ResponseModel):
    """An intake recorded for human review. It is never a lending decision; the policy behind it is synthetic."""

    application_id: ApplicationId
    customer_id: CustomerId
    product_code: CreditProductCode
    requested_amount: Money
    requested_term_months: int
    purpose: str
    declared_monthly_income: Money | None
    assessment_ref: AssessmentId | None
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime
    status_history: tuple[ApplicationStatusChange, ...]
    origin_conversation_id: ConversationId | None
    synthetic_policy: bool


class CreditApplicationListResponse(ResponseModel):
    applications: tuple[CreditApplicationView, ...]
