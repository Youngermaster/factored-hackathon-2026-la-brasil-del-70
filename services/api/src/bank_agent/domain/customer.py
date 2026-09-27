"""The customer, reduced to what the workflow and the evaluation breakdowns need.

Document numbers, phones, emails, birth dates, and addresses are deliberately absent: the identity adapter
(phase 05) owns the only lookup that needs them, so they never flow through the domain.
"""

from enum import StrEnum
from typing import Annotated

from pydantic import StringConstraints

from bank_agent.domain.base import DomainModel, Pii
from bank_agent.domain.identifiers import CustomerId
from bank_agent.domain.locale import Country


class CustomerSegment(StrEnum):
    PREMIUM = "premium"
    PLUS = "plus"
    BASIC = "basic"
    STUDENT = "student"


class CustomerStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class Customer(DomainModel):
    customer_id: CustomerId
    country: Country
    segment: CustomerSegment
    status: CustomerStatus
    first_name: Annotated[str, StringConstraints(min_length=1, max_length=100), Pii("name")]
