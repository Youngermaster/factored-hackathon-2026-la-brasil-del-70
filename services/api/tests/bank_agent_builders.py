"""Builders for valid domain objects in tests. Every value is synthetic and labeled as a fixture.

Each builder returns a valid object with sensible defaults; tests override only the fields they are about.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from bank_agent.domain.access import AuthLevel, Channel, Role
from bank_agent.domain.actions import ActionKind, ActionStatus
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.complaint import ComplaintCaseType, ComplaintChannel, HistoricalComplaint, Priority
from bank_agent.domain.conversation import Conversation, Turn, WorkflowPosition
from bank_agent.domain.customer import Customer, CustomerSegment, CustomerStatus
from bank_agent.domain.decision import ClauseRef, Decision, DecisionKind, RuleResult
from bank_agent.domain.dispute import DisputeCase, DisputeReason
from bank_agent.domain.execution_record import ExecutionRecord, LatencyBreakdown
from bank_agent.domain.handoff import (
    ActionTaken,
    EscalationReason,
    EscalationReasonCode,
    Handoff,
    HandoffAuth,
    HandoffRequest,
    VerificationStatus,
    VerifiedFact,
)
from bank_agent.domain.identifiers import (
    CaseId,
    ComplaintId,
    ConversationId,
    CustomerId,
    HandoffId,
    IdempotencyKey,
    LineageId,
    ProductId,
    SourceRef,
    TransactionId,
    TurnId,
)
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.masking import MaskedNumber
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.product import Product, ProductStatus, ProductType
from bank_agent.domain.session import Session
from bank_agent.domain.transaction import (
    FraudContext,
    Transaction,
    TransactionCategory,
    TransactionChannel,
    TransactionStatus,
    TransactionType,
)
from bank_agent.domain.workflow import Intent, Outcome, WorkflowRef

T0 = datetime(2026, 6, 10, 15, 0, tzinfo=UTC)
"""The fixed instant tests start from."""

CUSTOMER_A = CustomerId("CUS-A-0001")
CUSTOMER_B = CustomerId("CUS-B-0002")


def customer(customer_id: str = CUSTOMER_A, country: Country = Country.MX, **overrides: Any) -> Customer:
    fields: dict[str, Any] = {
        "customer_id": customer_id,
        "country": country,
        "segment": CustomerSegment.BASIC,
        "status": CustomerStatus.ACTIVE,
        "first_name": "Fixture",
    }
    return Customer.model_validate({**fields, **overrides})


def product(
    product_id: str = "PRD-A-CARD",
    customer_id: str = CUSTOMER_A,
    product_type: ProductType = ProductType.CREDIT_CARD,
    status: ProductStatus = ProductStatus.ACTIVE,
    currency: Currency = Currency.MXN,
    **extra: Any,
) -> Product:
    """``extra`` sets the optional fields added in phase 02b (balance, limit, rate, dates, days past due)."""
    return Product.model_validate(
        {
            "product_id": ProductId(product_id),
            "customer_id": CustomerId(customer_id),
            "product_type": product_type,
            "status": status,
            "masked_number": MaskedNumber.from_full("4000000000001234"),
            "currency": currency,
            **extra,
        }
    )


def transaction(
    transaction_id: str = "TXN-A-0001",
    customer_id: str = CUSTOMER_A,
    product_id: str = "PRD-A-CARD",
    amount: str = "1250.00",
    currency: Currency = Currency.MXN,
    occurred_at: datetime = T0 - timedelta(days=3),
    status: TransactionStatus = TransactionStatus.APPROVED,
    merchant_name: str | None = "FIXTURE MARKET",
    location_country: str = "MX",
    transaction_type: TransactionType = TransactionType.PURCHASE,
    channel: TransactionChannel = TransactionChannel.POS,
) -> Transaction:
    return Transaction(
        transaction_id=TransactionId(transaction_id),
        customer_id=CustomerId(customer_id),
        product_id=ProductId(product_id),
        occurred_at=occurred_at,
        transaction_type=transaction_type,
        category=TransactionCategory.FOOD,
        amount=Money.of(amount, currency),
        channel=channel,
        status=status,
        merchant_name=UntrustedText(merchant_name) if merchant_name is not None else None,
        location_country=location_country,
        fraud=FraudContext(label=False, score=Decimal("12.5")),
    )


def complaint(
    complaint_id: str = "CMP-A-0001", customer_id: str = CUSTOMER_A, created_at: datetime = T0 - timedelta(days=30)
) -> HistoricalComplaint:
    return HistoricalComplaint(
        complaint_id=ComplaintId(complaint_id),
        customer_id=CustomerId(customer_id),
        created_at=created_at,
        case_type=ComplaintCaseType.CLAIM,
        category="Cards",
        reception_channel=ComplaintChannel.APP,
        priority=Priority.MEDIUM,
    )


def idempotency_key(suffix: str = "0001") -> str:
    return IdempotencyKey(f"idem-key-fixture-{suffix}")


def dispute_case(
    case_id: str = "case-000001",
    txn: Transaction | None = None,
    opened_at: datetime = T0,
    key: str | None = None,
    reason: DisputeReason = DisputeReason.UNRECOGNIZED,
) -> DisputeCase:
    return DisputeCase.open(
        case_id=CaseId(case_id),
        transaction=txn if txn is not None else transaction(),
        reason=reason,
        opened_at=opened_at,
        sla_due_at=opened_at + timedelta(days=15),
        idempotency_key=IdempotencyKey(key if key is not None else idempotency_key(case_id[-4:])),
    )


def session(
    session_id: str = "ses-000001",
    customer_id: str | None = CUSTOMER_A,
    created_at: datetime = T0,
    role: Role = Role.CUSTOMER,
    staff_id: str | None = None,
) -> Session:
    return Session.model_validate(
        {
            "session_id": session_id,
            "lineage_id": f"lin-{session_id}",
            "role": role,
            "customer_id": customer_id,
            "staff_id": staff_id,
            "auth_level": AuthLevel.OTP_VERIFIED,
            "created_at": created_at,
            "last_seen_at": created_at,
            "idle_timeout": timedelta(minutes=15),
            "absolute_expires_at": created_at + timedelta(minutes=60),
        }
    )


def conversation(
    conversation_id: str = "conv-000001", customer_id: str = CUSTOMER_A, created_at: datetime = T0
) -> Conversation:
    return Conversation(
        conversation_id=ConversationId(conversation_id),
        customer_id=CustomerId(customer_id),
        lineage_id=LineageId("lin-ses-000001"),
        channel=Channel.WEB_CHAT,
        jurisdiction=Country.MX,
        position=WorkflowPosition(workflow=WorkflowRef(id="dispute", version=1), state="START"),
        created_at=created_at,
        updated_at=created_at,
    )


def turn(
    turn_id: str = "9b2f0d1e-0000-4000-8000-000000000001",
    conversation_id: str = "conv-000001",
    sequence: int = 1,
    text: str = "No reconozco un cargo",
) -> Turn:
    return Turn(
        turn_id=TurnId(turn_id),
        conversation_id=ConversationId(conversation_id),
        sequence=sequence,
        received_at=T0,
        customer_text=UntrustedText(text),
    )


def rule_result(
    rule_id: str = "DSP.within_window", passed: bool = True, clause: str = "DSP-MX-2.1@1", **overrides: Any
) -> RuleResult:
    fields: dict[str, Any] = {
        "rule_id": rule_id,
        "rule_version": 1,
        "passed": passed,
        "effect": None if passed else DecisionKind.DENY,
        "reason_code": "within_window" if passed else "window_closed",
        "params": {"window_days": 60, "days_since": 3},
        "clause_refs": [clause],
    }
    return RuleResult.model_validate({**fields, **overrides})


def decision(kind: DecisionKind = DecisionKind.ALLOW, results: tuple[RuleResult, ...] | None = None) -> Decision:
    return Decision.build(
        state="CHECK_ELIGIBILITY",
        action=ActionKind.CREATE_DISPUTE_CASE,
        kind=kind,
        rule_results=results if results is not None else (rule_result(),),
        policy_pack_version="pack-fixture-1",
    )


def handoff(**overrides: Any) -> Handoff:
    """A handoff exactly as phase 02 built it: a version 1.0.0 document with no 1.1.0 field.

    It pins ``schema_version`` because the model default moved to 1.1.0; use ``handoff_v1_1`` for new fields.
    """
    fields: dict[str, Any] = {
        "schema_version": "1.0.0",
        "handoff_id": HandoffId("ho-000001"),
        "created_at": T0,
        "conversation_ref": "conv-000001",
        "case_ref": "case-000001",
        "state_at_escalation": "CHECK_ELIGIBILITY",
        "language": Language.ES,
        "jurisdiction": Country.MX,
        "customer_ref": CUSTOMER_A,
        "auth": HandoffAuth(level=AuthLevel.OTP_VERIFIED, expires_at=T0 + timedelta(minutes=45)),
        "request": HandoffRequest(
            summary="Customer disputes an unrecognized card purchase.", intent=Intent.DISPUTE_NEW
        ),
        "verified_facts": [
            VerifiedFact(
                fact="Purchase of 1250.00 MXN on 2026-06-07", source=SourceRef.model_validate("transactions:TXN-A-0001")
            )
        ],
        "actions_taken": [
            ActionTaken(
                action=ActionKind.CREATE_DISPUTE_CASE,
                target=SourceRef.model_validate("transactions:TXN-A-0001"),
                confirmed=True,
                status=ActionStatus.EXECUTED,
                verification=VerificationStatus.VERIFIED,
                evidence=SourceRef.model_validate("dispute_cases:case-000001"),
            )
        ],
        "policy_basis": [ClauseRef.parse("ESC-MX-1.2@1")],
        "escalation_reason": EscalationReason(
            code=EscalationReasonCode.LEGAL_OR_REGULATOR_MENTION, detail="Customer mentioned the regulator."
        ),
        "open_questions": ["Whether the customer still holds the physical card."],
        "priority": Priority.HIGH,
        "sla_due": T0 + timedelta(hours=24),
    }
    return Handoff.model_validate({**fields, **overrides})


def handoff_v1_1(**overrides: Any) -> Handoff:
    """A version 1.1.0 handoff: the phase 02 document relabeled, ready for the fields added in 1.1.0."""
    return handoff(**{"schema_version": "1.1.0", **overrides})


def execution_record(turn_id: str = "9b2f0d1e-0000-4000-8000-000000000001", **overrides: Any) -> ExecutionRecord:
    fields: dict[str, Any] = {
        "turn_id": turn_id,
        "conversation_id": "conv-000001",
        "customer_ref": CUSTOMER_A,
        "workflow": WorkflowRef(id="dispute", version=1),
        "recorded_at": T0,
        "channel": Channel.WEB_CHAT,
        "language": Language.ES,
        "auth_level": AuthLevel.OTP_VERIFIED,
        "state_before": "UNDERSTAND",
        "state_after": "LOCATE_TRANSACTION",
        "outcome": Outcome.IN_PROGRESS,
        "decisions": [decision()],
        "policy_pack_version": "pack-fixture-1",
        "latency": LatencyBreakdown(total_ms=120, stages={"understand": 80}),
    }
    return ExecutionRecord.model_validate({**fields, **overrides})


def a_date(day: int = 7) -> date:
    return date(2026, 6, day)
