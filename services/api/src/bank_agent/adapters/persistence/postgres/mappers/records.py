"""Rows of conversations, turns, execution records, handoffs, and audit events."""

from typing import Any

from bank_agent.adapters.persistence.postgres.mappers.accounts import Row
from bank_agent.adapters.persistence.postgres.mappers.documents import (
    canonical_json,
    content_digest,
    document_of,
    json_object,
    load_document,
)
from bank_agent.domain.audit import AuditEvent
from bank_agent.domain.conversation import Conversation, Turn
from bank_agent.domain.execution_record import ExecutionRecord
from bank_agent.domain.handoff import HandoffRecord
from bank_agent.domain.identifiers import CustomerId


def conversation_to_row(conversation: Conversation) -> dict[str, Any]:
    return {
        "conversation_id": conversation.conversation_id,
        "customer_id": conversation.customer_id,
        "lineage_id": conversation.lineage_id,
        "status": conversation.status.value,
        "created_at": conversation.created_at,
        "version": conversation.version,
        "document": canonical_json(document_of(conversation)),
    }


def conversation_from_row(row: Row) -> Conversation:
    return load_document(Conversation, row["document"])


def turn_to_row(turn: Turn, customer_id: CustomerId) -> dict[str, Any]:
    return {
        "turn_id": turn.turn_id,
        "conversation_id": turn.conversation_id,
        "customer_id": customer_id,
        "sequence": turn.sequence,
        "received_at": turn.received_at,
        "document": canonical_json(document_of(turn)),
    }


def turn_from_row(row: Row) -> Turn:
    return load_document(Turn, row["document"])


def record_to_row(record: ExecutionRecord) -> dict[str, Any]:
    return {
        "turn_id": record.turn_id,
        "conversation_id": record.conversation_id,
        "customer_id": record.customer_ref,
        "recorded_at": record.recorded_at,
        "content_digest": content_digest(record),
        "document": canonical_json(document_of(record)),
    }


def record_from_row(row: Row) -> ExecutionRecord:
    return load_document(ExecutionRecord, row["document"])


def _lifecycle(record: HandoffRecord) -> dict[str, Any]:
    document = document_of(record)
    document.pop("handoff")
    return document


def handoff_to_row(record: HandoffRecord) -> dict[str, Any]:
    handoff = record.handoff
    review = handoff.credit_review
    return {
        "handoff_id": handoff.handoff_id,
        "customer_id": handoff.customer_ref,
        "case_ref": handoff.case_ref,
        "application_ref": review.application_ref if review is not None else None,
        "status": record.status.value,
        "priority": handoff.priority.value,
        "reason_code": handoff.escalation_reason.code.value,
        "language": handoff.language.value,
        "sla_due": handoff.sla_due,
        "content_digest": content_digest(handoff),
        "document": canonical_json(document_of(handoff)),
        "lifecycle": canonical_json(_lifecycle(record)),
    }


def handoff_from_row(row: Row) -> HandoffRecord:
    lifecycle = json_object(row["lifecycle"])
    combined = {**lifecycle, "handoff": json_object(row["document"])}
    return HandoffRecord.model_validate_json(canonical_json(combined))


def audit_to_row(event: AuditEvent, customer_id: str | None) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "occurred_at": event.occurred_at,
        "customer_id": customer_id,
        "actor_role": event.actor_role.value if event.actor_role is not None else None,
        "action": event.action,
        "outcome": event.outcome.value,
        "content_digest": content_digest(event),
        "document": canonical_json(document_of(event)),
    }


def audit_from_row(row: Row) -> AuditEvent:
    return load_document(AuditEvent, row["document"])
