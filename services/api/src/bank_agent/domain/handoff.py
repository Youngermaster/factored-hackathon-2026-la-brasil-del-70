"""The handoff to a human agent, version 1 (``contracts/schemas/handoff.v1.json``), minor version 1.1.

A handoff carries the request, verified facts with their sources, the actions taken with their verification
status, the policy basis, the escalation reason, and the open questions. It never carries a raw transcript:
unknown keys are rejected at every level, every free-text field is length-capped, and the request summary is a
single paragraph. The customer is referenced by internal id only. See ADR 0006.

Version 1.1.0 adds the workflow, the credit review (with the risk estimate, which agents see and customers
never do), and the card request. Those fields are marked ``AddedIn``, so stored 1.0.0 documents stay valid.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, StringConstraints, model_validator

from bank_agent.domain.access import AuthLevel
from bank_agent.domain.actions import ActionKind, ActionStatus
from bank_agent.domain.base import (
    AddedIn,
    DomainModel,
    Pii,
    SingleLineText,
    SummaryText,
    UtcDatetime,
    check_added_fields,
)
from bank_agent.domain.cards import CardAction, CardRequest
from bank_agent.domain.complaint import Priority
from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.eligibility import CreditReview
from bank_agent.domain.errors import InvalidHandoffTransitionError
from bank_agent.domain.escalation import EscalationReasonCode as EscalationReasonCode
from bank_agent.domain.identifiers import CaseId, ConversationId, CustomerId, HandoffId, SourceRef, StaffId
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.workflow import Intent, StateName, WorkflowRef

SchemaVersion = Annotated[str, StringConstraints(pattern=r"^1\.[0-9]+\.[0-9]+$")]
MAX_VERIFIED_FACTS = 20
MAX_ACTIONS = 10
MAX_OPEN_QUESTIONS = 10
CREDIT_REVIEW_CODES = frozenset(
    {EscalationReasonCode.CREDIT_REVIEW_REQUIRED, EscalationReasonCode.ELIGIBILITY_CONTESTED}
)
CARD_REQUEST_CODES = {
    EscalationReasonCode.CARD_UNBLOCK_REQUESTED: CardAction.UNBLOCK_REQUEST,
    EscalationReasonCode.CARD_REPLACEMENT_REQUESTED: CardAction.REPLACEMENT_REQUEST,
}


class HandoffAuth(DomainModel):
    level: AuthLevel
    expires_at: UtcDatetime


class HandoffRequest(DomainModel):
    summary: SummaryText
    intent: Intent


class VerifiedFact(DomainModel):
    """A fact the system verified, with the record that proves it (``table:id``)."""

    fact: SingleLineText
    source: SourceRef


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    NOT_VERIFIED = "not_verified"
    MISMATCH = "mismatch"


class ActionTaken(DomainModel):
    action: ActionKind
    target: SourceRef
    confirmed: bool
    status: ActionStatus
    verification: VerificationStatus
    evidence: SourceRef | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.verification is VerificationStatus.VERIFIED:
            if self.status is not ActionStatus.EXECUTED:
                raise ValueError("only an executed action can be verified")
            if self.evidence is None:
                raise ValueError("a verified action needs an evidence reference")
        if self.status is ActionStatus.EXECUTED and not self.confirmed:
            raise ValueError("an executed action must have been confirmed by the customer")
        return self


class EscalationReason(DomainModel):
    code: EscalationReasonCode
    detail: SingleLineText


class Sentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    VERY_NEGATIVE = "very_negative"
    UNKNOWN = "unknown"


class Handoff(DomainModel):
    schema_version: SchemaVersion = "1.2.0"
    handoff_id: HandoffId
    created_at: UtcDatetime
    conversation_ref: ConversationId
    case_ref: CaseId | None = None
    state_at_escalation: StateName
    language: Language
    jurisdiction: Country
    customer_ref: CustomerId
    auth: HandoffAuth
    request: HandoffRequest
    verified_facts: Annotated[tuple[VerifiedFact, ...], Field(max_length=MAX_VERIFIED_FACTS)] = ()
    actions_taken: Annotated[tuple[ActionTaken, ...], Field(max_length=MAX_ACTIONS)] = ()
    policy_basis: tuple[ClauseRef, ...] = ()
    escalation_reason: EscalationReason
    open_questions: Annotated[tuple[SingleLineText, ...], Field(max_length=MAX_OPEN_QUESTIONS)] = ()
    customer_sentiment: Sentiment = Sentiment.UNKNOWN
    priority: Priority
    sla_due: UtcDatetime
    workflow: Annotated[WorkflowRef | None, AddedIn("1.1.0")] = None
    credit_review: Annotated[CreditReview | None, AddedIn("1.1.0")] = None
    card_request: Annotated[CardRequest | None, AddedIn("1.1.0")] = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.language is Language.EN:
            raise ValueError("customer conversations, and so handoffs, are in Spanish or Portuguese")
        if self.sla_due < self.created_at:
            raise ValueError("sla_due cannot precede created_at")
        check_added_fields(self, self.schema_version)
        code = self.escalation_reason.code
        if code in CREDIT_REVIEW_CODES and self.credit_review is None:
            raise ValueError(f"escalation reason {code} needs a credit_review")
        expected_action = CARD_REQUEST_CODES.get(code)
        if expected_action is not None and (
            self.card_request is None or self.card_request.action is not expected_action
        ):
            raise ValueError(f"escalation reason {code} needs a card_request for {expected_action}")
        return self


class HandoffStatus(StrEnum):
    OPEN = "open"
    CLAIMED = "claimed"
    RESOLVED = "resolved"


class HandoffOutcomeCode(StrEnum):
    RESOLVED_BY_AGENT = "resolved_by_agent"
    CASE_UPDATED = "case_updated"
    REFERRED_TO_SPECIALIST = "referred_to_specialist"
    NO_ACTION_NEEDED = "no_action_needed"
    CUSTOMER_UNREACHABLE = "customer_unreachable"
    OTHER = "other"


class HandoffResolution(DomainModel):
    outcome: HandoffOutcomeCode
    note: Annotated[str, StringConstraints(max_length=500), Pii("free_text")] = ""
    resolved_by: StaffId
    resolved_at: UtcDatetime


class HandoffRecord(DomainModel):
    """The immutable handoff document plus its lifecycle in the agent inbox: open, claimed, resolved."""

    handoff: Handoff
    status: HandoffStatus = HandoffStatus.OPEN
    claimed_by: StaffId | None = None
    claimed_at: UtcDatetime | None = None
    resolution: HandoffResolution | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        claimed = self.claimed_by is not None and self.claimed_at is not None
        unclaimed = self.claimed_by is None and self.claimed_at is None
        if self.status is HandoffStatus.OPEN and not (unclaimed and self.resolution is None):
            raise ValueError("an open handoff is neither claimed nor resolved")
        if self.status is HandoffStatus.CLAIMED and not (claimed and self.resolution is None):
            raise ValueError("a claimed handoff names the agent and is not resolved")
        if self.status is HandoffStatus.RESOLVED and not (claimed and self.resolution is not None):
            raise ValueError("a resolved handoff was claimed and has a resolution")
        return self

    @property
    def handoff_id(self) -> str:
        return self.handoff.handoff_id

    def claim(self, staff_id: StaffId, at: datetime) -> Self:
        if self.status is not HandoffStatus.OPEN:
            raise InvalidHandoffTransitionError("only an open handoff can be claimed")
        return self.evolve(status=HandoffStatus.CLAIMED, claimed_by=staff_id, claimed_at=at)

    def resolve(self, staff_id: StaffId, outcome: HandoffOutcomeCode, note: str, at: datetime) -> Self:
        if self.status is not HandoffStatus.CLAIMED or self.claimed_by != staff_id:
            raise InvalidHandoffTransitionError("only the agent who claimed a handoff can resolve it")
        resolution = HandoffResolution(outcome=outcome, note=note, resolved_by=staff_id, resolved_at=at)
        return self.evolve(status=HandoffStatus.RESOLVED, resolution=resolution)
