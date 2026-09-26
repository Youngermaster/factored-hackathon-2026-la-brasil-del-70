"""Historical complaints, limited to intake-time fields.

Post-outcome fields (status, resolution, compensation, satisfaction, SLA breach) and the untrusted free-text
description are deliberately absent: they are a leakage path for intake-time decisions and an injection surface.
"""

from enum import StrEnum
from typing import Annotated

from pydantic import StringConstraints

from bank_agent.domain.base import DomainModel, UtcDatetime
from bank_agent.domain.identifiers import ComplaintId, CustomerId, ProductId
from bank_agent.domain.money import Money


class ComplaintCaseType(StrEnum):
    COMPLAINT = "complaint"
    CLAIM = "claim"
    REQUEST = "request"
    SUGGESTION = "suggestion"


class ComplaintChannel(StrEnum):
    CALL_CENTER = "call_center"
    EMAIL = "email"
    WEB = "web"
    APP = "app"
    BRANCH = "branch"
    REGULATOR = "regulator"


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


Category = Annotated[str, StringConstraints(min_length=1, max_length=100)]


class HistoricalComplaint(DomainModel):
    complaint_id: ComplaintId
    customer_id: CustomerId
    created_at: UtcDatetime
    case_type: ComplaintCaseType
    category: Category
    subcategory: Category | None = None
    reception_channel: ComplaintChannel
    affected_product_id: ProductId | None = None
    claimed_amount: Money | None = None
    priority: Priority
