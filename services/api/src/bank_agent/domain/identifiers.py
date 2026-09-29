"""Typed identifiers and references.

Each identifier is a ``NewType`` over ``str`` wrapped in ``Annotated`` constraints. mypy treats every kind as
distinct (a ``CustomerId`` is not a ``ProductId``), Pydantic validates the pattern and length, and calling the
name builds a value: ``CustomerId("C000123")``. Values are plain strings at runtime.

``SessionId`` is an internal, loggable handle for a session, never the secret token the client holds.
"""

from enum import StrEnum
from typing import Annotated, NewType, Self

from pydantic import GetJsonSchemaHandler, StringConstraints, model_serializer, model_validator
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from bank_agent.domain.base import DomainModel

ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]*$"


def _constraint(max_length: int) -> StringConstraints:
    return StringConstraints(pattern=ID_PATTERN, min_length=1, max_length=max_length)


_CustomerId = NewType("_CustomerId", str)
_ProductId = NewType("_ProductId", str)
_TransactionId = NewType("_TransactionId", str)
_ComplaintId = NewType("_ComplaintId", str)
_CaseId = NewType("_CaseId", str)
_ConversationId = NewType("_ConversationId", str)
_TurnId = NewType("_TurnId", str)
_SessionId = NewType("_SessionId", str)
_LineageId = NewType("_LineageId", str)
_HandoffId = NewType("_HandoffId", str)
_AuditEventId = NewType("_AuditEventId", str)
_ChallengeId = NewType("_ChallengeId", str)
_PersonaId = NewType("_PersonaId", str)
_StaffId = NewType("_StaffId", str)
_IdempotencyKey = NewType("_IdempotencyKey", str)
_TraceId = NewType("_TraceId", str)
_ApplicationId = NewType("_ApplicationId", str)
_RiskEstimateId = NewType("_RiskEstimateId", str)
_AssessmentId = NewType("_AssessmentId", str)
_CreditProductCode = NewType("_CreditProductCode", str)
_CorrelationId = NewType("_CorrelationId", str)
_ModelCallId = NewType("_ModelCallId", str)
_ToolCallId = NewType("_ToolCallId", str)

CustomerId = Annotated[_CustomerId, _constraint(20)]
ProductId = Annotated[_ProductId, _constraint(20)]
TransactionId = Annotated[_TransactionId, _constraint(30)]
ComplaintId = Annotated[_ComplaintId, _constraint(30)]
CaseId = Annotated[_CaseId, _constraint(64)]
ConversationId = Annotated[_ConversationId, _constraint(64)]
TurnId = Annotated[_TurnId, _constraint(64)]
"""Client-supplied (a UUID per message), so a retried request is recognized and replayed."""
SessionId = Annotated[_SessionId, _constraint(64)]
LineageId = Annotated[_LineageId, _constraint(64)]
"""Stable across session rotation and re-authentication into the same conversation; keys the trust state."""
HandoffId = Annotated[_HandoffId, _constraint(64)]
AuditEventId = Annotated[_AuditEventId, _constraint(64)]
ChallengeId = Annotated[_ChallengeId, _constraint(64)]
PersonaId = Annotated[_PersonaId, _constraint(64)]
StaffId = Annotated[_StaffId, _constraint(64)]
IdempotencyKey = Annotated[_IdempotencyKey, StringConstraints(pattern=r"^[A-Za-z0-9_-]{16,128}$")]
TraceId = Annotated[_TraceId, StringConstraints(pattern=r"^[0-9a-f]{32}$")]
ApplicationId = Annotated[_ApplicationId, _constraint(64)]
"""A credit application intake recorded for human review."""
RiskEstimateId = Annotated[_RiskEstimateId, _constraint(64)]
AssessmentId = Annotated[_AssessmentId, _constraint(64)]
"""An assessment of the synthetic eligibility service."""
CreditProductCode = Annotated[_CreditProductCode, StringConstraints(pattern=r"^[A-Z][A-Z0-9_-]{2,31}$")]
"""A public code of a synthetic credit catalog entry, for example ``MX-CC-CLASSIC``."""
CorrelationId = Annotated[_CorrelationId, StringConstraints(pattern=r"^[A-Za-z0-9-]{8,64}$")]
"""The id of one HTTP request (``X-Request-ID``), carried to every service, tool call, model call, and record it
causes, so a customer turn can be followed from the API to PostgreSQL and the model traces."""
ModelCallId = Annotated[_ModelCallId, _constraint(64)]
"""One logical language model call (all its retries and its repair), unique across turns."""
ToolCallId = Annotated[_ToolCallId, _constraint(64)]
"""One tool call within a turn, unique across turns."""


class IdKind(StrEnum):
    """Kinds of identifiers the ``IdGenerator`` port creates. The value is the identifier prefix."""

    CASE = "case"
    CONVERSATION = "conv"
    TURN = "turn"
    SESSION = "ses"
    LINEAGE = "lin"
    HANDOFF = "ho"
    AUDIT_EVENT = "aud"
    CHALLENGE = "chl"
    APPLICATION = "app"
    RISK_ESTIMATE = "rsk"
    ASSESSMENT = "elg"
    MODEL_CALL = "mc"
    TOOL_CALL = "tc"


class SourceTable(StrEnum):
    """Tables a verified fact or an evidence reference may point to."""

    CUSTOMERS = "customers"
    PRODUCTS = "products"
    TRANSACTIONS = "transactions"
    DISPUTE_CASES = "dispute_cases"
    HISTORICAL_COMPLAINTS = "historical_complaints"
    CONVERSATIONS = "conversations"
    TURNS = "turns"
    EXECUTION_RECORDS = "execution_records"
    HANDOFFS = "handoffs"
    AUDIT_EVENTS = "audit_events"
    POLICY_CLAUSES = "policy_clauses"
    CREDIT_APPLICATIONS = "credit_applications"
    CREDIT_PRODUCTS = "credit_products"
    ELIGIBILITY_ASSESSMENTS = "eligibility_assessments"


_SOURCE_KEY_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.@-]{0,127}$"
SOURCE_REF_PATTERN = rf"^({'|'.join(table.value for table in SourceTable)}):[A-Za-z0-9][A-Za-z0-9_.@-]{{0,127}}$"


class SourceRef(DomainModel):
    """A pointer to the record that proves a fact, serialized as one string: ``table:id``."""

    table: SourceTable
    key: Annotated[str, StringConstraints(pattern=_SOURCE_KEY_PATTERN)]

    @model_validator(mode="before")
    @classmethod
    def _parse_string(cls, value: object) -> object:
        if isinstance(value, str):
            table, separator, key = value.partition(":")
            if not separator:
                raise ValueError("a source reference has the form table:id")
            return {"table": table, "key": key}
        return value

    @model_serializer(mode="plain", when_used="always")
    def _serialize(self) -> str:
        return str(self)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler, /) -> JsonSchemaValue:
        return {"type": "string", "pattern": SOURCE_REF_PATTERN, "title": "SourceRef"}

    @classmethod
    def of(cls, table: SourceTable, key: str) -> Self:
        return cls(table=table, key=key)

    def __str__(self) -> str:
        return f"{self.table.value}:{self.key}"
