"""Identification and one-time-code challenges for the mock identity provider (phase 05).

Identification alone never grants access: it only opens a one-time-code challenge. Codes and document data
are excluded from ``repr`` and marked as personal data.
"""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, NonNegativeInt, StringConstraints, model_validator

from bank_agent.domain.access import AuthLevel, Role, check_subject
from bank_agent.domain.base import DomainModel, Pii, UtcDatetime
from bank_agent.domain.identifiers import ChallengeId, CustomerId, PersonaId, StaffId

OtpCode = Annotated[str, StringConstraints(pattern=r"^[0-9]{6}$"), Pii("credential")]


class OtpPurpose(StrEnum):
    LOGIN = "login"
    STEP_UP = "step_up"


class PersonaIdentification(DomainModel):
    kind: Literal["persona"] = "persona"
    persona_id: PersonaId


class DocumentIdentification(DomainModel):
    """A document number plus the last four digits of the phone on file. Never proof of identity by itself."""

    kind: Literal["document"] = "document"
    document_number: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9-]{4,20}$"), Pii("document_number")] = Field(
        repr=False
    )
    phone_last4: Annotated[str, StringConstraints(pattern=r"^[0-9]{4}$"), Pii("phone")] = Field(repr=False)


Identification = Annotated[PersonaIdentification | DocumentIdentification, Field(discriminator="kind")]


class OtpDeliveryReceipt(DomainModel):
    """What the sender reports. ``demo_code`` is set only when demo mode is on, so the UI can show it labeled."""

    delivered: bool
    channel: Literal["demo", "sms"]
    demo_code: OtpCode | None = Field(default=None, repr=False)


class OtpDispatch(DomainModel):
    """A code to deliver. The sender resolves the destination from the recipient; the domain holds no phone."""

    challenge_id: ChallengeId
    purpose: OtpPurpose
    recipient_customer_id: CustomerId | None = None
    recipient_staff_id: StaffId | None = None
    code: OtpCode = Field(repr=False)
    expires_at: UtcDatetime

    @model_validator(mode="after")
    def _validate_recipient(self) -> Self:
        if (self.recipient_customer_id is None) == (self.recipient_staff_id is None):
            raise ValueError("a dispatch has exactly one recipient")
        return self


class OtpChallenge(DomainModel):
    challenge_id: ChallengeId
    purpose: OtpPurpose
    expires_at: UtcDatetime
    attempts_remaining: NonNegativeInt
    delivery: OtpDeliveryReceipt


class VerifiedIdentity(DomainModel):
    role: Role
    customer_id: CustomerId | None = None
    staff_id: StaffId | None = None
    auth_level: AuthLevel
    verified_at: UtcDatetime

    @model_validator(mode="after")
    def _validate(self) -> Self:
        check_subject(self.role, self.customer_id, self.staff_id)
        if not self.auth_level.satisfies(AuthLevel.OTP_VERIFIED) or self.auth_level is AuthLevel.STEP_UP:
            raise ValueError("a verified identity is exactly otp_verified")
        return self
