"""Mapper round trips: domain object to row and back gives the same object (no database needed)."""

from datetime import timedelta

from bank_agent.adapters.persistence.postgres.mappers.accounts import (
    customer_from_row,
    customer_to_row,
    product_from_row,
    product_to_row,
    transaction_from_row,
    transaction_to_row,
)
from bank_agent.adapters.persistence.postgres.mappers.cases import (
    application_from_row,
    application_to_row,
    case_from_row,
    case_to_row,
)
from bank_agent.adapters.persistence.postgres.mappers.documents import content_digest
from bank_agent.adapters.persistence.postgres.mappers.history import (
    complaint_from_row,
    complaint_to_row,
    credit_profile_from_row,
    credit_profile_to_row,
)
from bank_agent.adapters.persistence.postgres.mappers.records import (
    audit_from_row,
    audit_to_row,
    conversation_from_row,
    conversation_to_row,
    handoff_from_row,
    handoff_to_row,
    record_from_row,
    record_to_row,
    turn_from_row,
    turn_to_row,
)
from bank_agent.adapters.persistence.postgres.mappers.sessions import (
    session_from_row,
    session_to_row,
    trust_event_from_row,
    trust_event_to_row,
)
from bank_agent.domain.audit import AuditEvent, AuditOutcome
from bank_agent.domain.handoff import HandoffRecord
from bank_agent.domain.identifiers import AuditEventId, CustomerId, LineageId, StaffId
from bank_agent.domain.locale import Language
from bank_agent.domain.trust import TrustEvent, TrustEventKind
from bank_agent_builders import (
    T0,
    complaint,
    conversation,
    customer,
    dispute_case,
    execution_record,
    handoff_v1_1,
    session,
    transaction,
    turn,
)
from bank_agent_contracts import contract_dataset, existing_application
from bank_agent_credit import credit_profiles


def test_core_banking_rows_round_trip() -> None:
    data = contract_dataset()
    assert customer_from_row(customer_to_row(customer())) == customer()
    for item in data.products:
        assert product_from_row(product_to_row(item)) == item
    for txn in data.transactions:
        assert transaction_from_row(transaction_to_row(txn)) == txn
    assert complaint_from_row(complaint_to_row(complaint())) == complaint()
    for profile in credit_profiles():
        assert credit_profile_from_row(credit_profile_to_row(profile)) == profile


def test_document_rows_round_trip() -> None:
    case = dispute_case("case-000009", txn=transaction("TXN-A-0001"))
    assert case_from_row(case_to_row(case)) == case
    assert application_from_row(application_to_row(existing_application())) == existing_application()
    assert conversation_from_row(conversation_to_row(conversation())) == conversation()
    assert turn_from_row(turn_to_row(turn(), CustomerId("CUS-A-0001"))) == turn()
    record = execution_record()
    assert record_from_row(record_to_row(record)) == record


def test_handoff_rows_keep_the_document_and_the_lifecycle_apart() -> None:
    record = HandoffRecord(handoff=handoff_v1_1()).claim(StaffId("agent-0001"), T0 + timedelta(minutes=2))
    row = handoff_to_row(record)
    assert handoff_from_row(row) == record
    assert row["content_digest"] == content_digest(record.handoff)
    assert "handoff" not in row["lifecycle"]


def test_session_and_trust_rows_round_trip() -> None:
    current = session().evolve(language_preference=Language.PT)
    assert session_from_row(session_to_row(current)) == current
    event = TrustEvent(kind=TrustEventKind.FAILED_OTP, occurred_at=T0, detector="otp:provider@1", detail_code="x")
    assert trust_event_from_row(trust_event_to_row(LineageId("lin-1"), 1, event)) == event


def test_audit_rows_round_trip_and_digests_are_stable() -> None:
    event = AuditEvent(
        event_id=AuditEventId("aud-000001"), occurred_at=T0, action="block_card", outcome=AuditOutcome.SUCCESS
    )
    row = audit_to_row(event, "CUS-A-0001")
    assert audit_from_row(row) == event
    assert row["customer_id"] == "CUS-A-0001"
    assert content_digest(event) == content_digest(AuditEvent.model_validate(event.model_dump()))
    assert content_digest(event) != content_digest(event.evolve(outcome=AuditOutcome.FAILURE))
