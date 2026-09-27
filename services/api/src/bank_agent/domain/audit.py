"""Audit events: an append-only log of security-relevant actions (tool calls, logins, handoff claims)."""

from enum import StrEnum
from typing import Annotated

from pydantic import Field, JsonValue, StringConstraints

from bank_agent.domain.access import Role
from bank_agent.domain.base import Code, DomainModel, UtcDatetime
from bank_agent.domain.identifiers import AuditEventId, SourceRef, TraceId

ActorRef = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")]


class AuditOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"


class AuditEvent(DomainModel):
    """One audit entry. ``arguments`` are already redacted by the caller; the log never redacts for it."""

    event_id: AuditEventId
    occurred_at: UtcDatetime
    actor_role: Role | None = None
    actor_ref: ActorRef | None = None
    action: Code
    target: SourceRef | None = None
    outcome: AuditOutcome
    arguments: dict[str, JsonValue] = Field(default_factory=dict)
    request_id: Annotated[str, StringConstraints(max_length=128)] | None = None
    trace_id: TraceId | None = None
