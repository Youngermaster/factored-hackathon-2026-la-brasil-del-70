"""Persisted, untrusted messages exchanged during an authorized human handoff."""

from enum import StrEnum
from typing import Annotated

from pydantic import Field, StringConstraints

from bank_agent.domain.base import DomainModel, Pii, UntrustedText, UtcDatetime
from bank_agent.domain.identifiers import ConversationId, HandoffId

HumanMessageId = Annotated[str, StringConstraints(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
HumanMessageText = Annotated[UntrustedText, StringConstraints(min_length=1, max_length=4000), Pii("free_text")]


class HumanMessageRole(StrEnum):
    CUSTOMER = "user"
    AGENT = "agent"


class HumanServiceStatus(StrEnum):
    QUEUED = "queued"
    JOINED = "joined"
    CLOSED = "closed"


class HumanMessage(DomainModel):
    message_id: HumanMessageId
    conversation_id: ConversationId
    handoff_id: HandoffId
    sequence: Annotated[int, Field(gt=0)]
    sent_at: UtcDatetime
    role: HumanMessageRole
    text: HumanMessageText


class HumanServiceView(DomainModel):
    """Customer-safe lifecycle and message page, with no staff or credit-profile identifiers."""

    conversation_id: ConversationId
    handoff_id: HandoffId
    status: HumanServiceStatus
    queued_at: UtcDatetime
    joined_at: UtcDatetime | None
    closed_at: UtcDatetime | None
    messages: tuple[HumanMessage, ...]


class HumanMessageReceipt(DomainModel):
    message: HumanMessage
    replayed: bool
