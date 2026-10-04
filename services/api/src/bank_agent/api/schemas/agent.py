"""Agent console requests and responses: handoffs with their lifecycle, and credit application intakes.

The handoff view is the structured handoff (request summary, verified facts, actions taken, policy basis, open
questions); it never includes a transcript. Agents see the credit review's internal risk estimate (phase 02b rule).
``policy_excerpts`` adds, per policy basis clause the loaded pack resolves, the clause text rendered in the handoff's
language exactly as the engine renders customer citations. It is a view field only: the handoff contract is unchanged.
"""

from collections.abc import Iterable
from datetime import datetime
from typing import Annotated

from pydantic import Field, StringConstraints

from bank_agent.api.provider import PolicyClauses
from bank_agent.api.schemas.base import RequestModel, ResponseModel
from bank_agent.application.engine.render import MAX_EXCERPT
from bank_agent.domain.cards import CardRequest
from bank_agent.domain.complaint import Priority
from bank_agent.domain.conversation import Citation
from bank_agent.domain.credit import ApplicationStatus, ApplicationStatusChange
from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.eligibility import CreditReview
from bank_agent.domain.errors import PolicyClauseNotFoundError
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
from bank_agent.domain.locale import Country, Language, Locale
from bank_agent.domain.money import Money
from bank_agent.domain.workflow import StateName, WorkflowRef
from bank_agent.policy.explain import render_body


def policy_excerpts(
    clauses: PolicyClauses, refs: Iterable[ClauseRef], language: Language, jurisdiction: Country
) -> tuple[Citation, ...]:
    """One citation per clause in ``refs``, in order, rendered in ``language`` for the jurisdiction's locale.

    A reference the pack cannot resolve (an unknown clause, version, or language) is left out: no text is invented.
    """
    locale = Locale.for_customer(jurisdiction, language)
    citations: list[Citation] = []
    for ref in refs:
        try:
            clause = clauses.get_clause(ref.clause_id, language, ref.version)
        except PolicyClauseNotFoundError:
            continue
        excerpt = render_body(clause, locale)[:MAX_EXCERPT]
        if excerpt:
            citations.append(Citation(clause=ref, excerpt=excerpt))
    return tuple(citations)


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
    policy_excerpts: tuple[Citation, ...]
    """The policy basis clauses the loaded pack resolves, in order, with their text in the handoff's language."""
    escalation_reason: EscalationReason
    open_questions: tuple[str, ...]
    customer_sentiment: Sentiment
    priority: Priority
    sla_due: datetime
    credit_review: CreditReview | None
    card_request: CardRequest | None

    @classmethod
    def of(cls, record: HandoffRecord, clauses: PolicyClauses) -> "HandoffView":
        document = record.handoff
        fields = {name: getattr(document, name) for name in cls.model_fields if hasattr(document, name)}
        fields.update(
            policy_excerpts=policy_excerpts(clauses, document.policy_basis, document.language, document.jurisdiction),
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
    version: int = Field(description="Send it back as `expected_version` to move the intake (review, close).")
    created_at: datetime
    updated_at: datetime
    status_history: tuple[ApplicationStatusChange, ...]
    origin_conversation_id: ConversationId | None
    synthetic_policy: bool


class CreditApplicationMoveRequest(RequestModel):
    """Take an intake into human review, or close it; the version it was read at guards against a concurrent move."""

    expected_version: Annotated[int, Field(ge=0, le=1_000_000)]


class CreditApplicationListResponse(ResponseModel):
    applications: tuple[CreditApplicationView, ...]
