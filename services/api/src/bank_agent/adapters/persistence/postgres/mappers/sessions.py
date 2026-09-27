"""Rows of ``sessions`` and ``trust_events``."""

from datetime import timedelta
from typing import Any

from bank_agent.adapters.persistence.postgres.mappers.accounts import Row
from bank_agent.adapters.persistence.postgres.mappers.documents import (
    canonical_json,
    content_digest,
    document_of,
    load_document,
)
from bank_agent.domain.access import AuthLevel, Role
from bank_agent.domain.identifiers import CustomerId, LineageId, SessionId, StaffId
from bank_agent.domain.locale import Language
from bank_agent.domain.session import Session
from bank_agent.domain.trust import TrustEvent


def session_to_row(session: Session) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "lineage_id": session.lineage_id,
        "role": session.role.value,
        "customer_id": session.customer_id,
        "staff_id": session.staff_id,
        "auth_level": session.auth_level.value,
        "created_at": session.created_at,
        "last_seen_at": session.last_seen_at,
        "idle_timeout_seconds": int(session.idle_timeout.total_seconds()),
        "absolute_expires_at": session.absolute_expires_at,
        "step_up_expires_at": session.step_up_expires_at,
        "revoked_at": session.revoked_at,
        "language_preference": session.language_preference.value if session.language_preference else None,
    }


def session_from_row(row: Row) -> Session:
    customer = row["customer_id"]
    staff = row["staff_id"]
    language = row["language_preference"]
    return Session(
        session_id=SessionId(row["session_id"]),
        lineage_id=LineageId(row["lineage_id"]),
        role=Role(row["role"]),
        customer_id=CustomerId(customer) if customer is not None else None,
        staff_id=StaffId(staff) if staff is not None else None,
        auth_level=AuthLevel(row["auth_level"]),
        created_at=row["created_at"],
        last_seen_at=row["last_seen_at"],
        idle_timeout=timedelta(seconds=row["idle_timeout_seconds"]),
        absolute_expires_at=row["absolute_expires_at"],
        step_up_expires_at=row["step_up_expires_at"],
        revoked_at=row["revoked_at"],
        language_preference=Language(language) if language is not None else None,
    )


def trust_event_to_row(lineage_id: LineageId, sequence: int, event: TrustEvent) -> dict[str, Any]:
    return {
        "lineage_id": lineage_id,
        "sequence": sequence,
        "occurred_at": event.occurred_at,
        "content_digest": content_digest(event),
        "document": canonical_json(document_of(event)),
    }


def trust_event_from_row(row: Row) -> TrustEvent:
    return load_document(TrustEvent, row["document"])
