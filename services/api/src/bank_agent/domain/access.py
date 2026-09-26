"""Authentication levels, roles, channels, and the access context that scopes every repository."""

from enum import StrEnum
from typing import Self

from pydantic import model_validator

from bank_agent.domain.base import DomainModel
from bank_agent.domain.identifiers import CustomerId, SessionId, StaffId


class AuthLevel(StrEnum):
    """How strongly the session's subject is authenticated, from weakest to strongest."""

    NONE = "none"
    IDENTIFIED = "identified"
    OTP_VERIFIED = "otp_verified"
    STEP_UP = "step_up"

    @property
    def rank(self) -> int:
        return _AUTH_RANKS[self]

    def satisfies(self, required: "AuthLevel") -> bool:
        return self.rank >= required.rank


_AUTH_RANKS = {AuthLevel.NONE: 0, AuthLevel.IDENTIFIED: 1, AuthLevel.OTP_VERIFIED: 2, AuthLevel.STEP_UP: 3}


class Role(StrEnum):
    CUSTOMER = "customer"
    AGENT = "agent"
    EVALUATOR = "evaluator"


class Channel(StrEnum):
    """The service channel a conversation runs on (not the channel of a transaction)."""

    WEB_CHAT = "web_chat"
    AGENT_CONSOLE = "agent_console"
    EVALUATION_HARNESS = "evaluation_harness"


class AccessContext(DomainModel):
    """Who is asking. Repositories are bound to one context and scope every query by it.

    This is the "session context" of phase 05: the PostgreSQL unit of work sets ``app.customer_id`` and
    ``app.role`` from it inside each transaction. A customer context always names the customer; a staff
    context (agent or evaluator) names the staff member and never a customer.
    """

    role: Role
    customer_id: CustomerId | None = None
    staff_id: StaffId | None = None
    session_id: SessionId | None = None

    @model_validator(mode="after")
    def _validate_subject(self) -> Self:
        if self.role is Role.CUSTOMER:
            if self.customer_id is None or self.staff_id is not None:
                raise ValueError("a customer context names the customer and no staff member")
        elif self.staff_id is None or self.customer_id is not None:
            raise ValueError("a staff context names the staff member and no customer")
        return self

    @classmethod
    def for_customer(cls, customer_id: CustomerId, session_id: SessionId | None = None) -> Self:
        return cls(role=Role.CUSTOMER, customer_id=customer_id, session_id=session_id)

    @classmethod
    def for_staff(cls, role: Role, staff_id: StaffId, session_id: SessionId | None = None) -> Self:
        return cls(role=role, staff_id=staff_id, session_id=session_id)
