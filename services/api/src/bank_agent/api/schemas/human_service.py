"""Allowlisted human-service API bodies: no author, customer, staff, or credit identifiers in requests."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import StringConstraints

from bank_agent.api.schemas.base import RequestModel, ResponseModel
from bank_agent.domain.base import Pii
from bank_agent.domain.human_service import HumanMessage, HumanServiceStatus
from bank_agent.domain.identifiers import ConversationId, HandoffId


class SendHumanMessageRequest(RequestModel):
    message_id: UUID
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000), Pii("free_text")]


class HumanServiceResponse(ResponseModel):
    conversation_id: ConversationId
    handoff_id: HandoffId
    status: HumanServiceStatus
    queued_at: datetime
    joined_at: datetime | None
    closed_at: datetime | None
    messages: tuple[HumanMessage, ...]


class HumanMessageResponse(ResponseModel):
    message: HumanMessage
    replayed: bool
