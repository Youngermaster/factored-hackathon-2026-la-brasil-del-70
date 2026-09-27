"""Authentication requests and responses."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from bank_agent.api.schemas.base import RequestModel, ResponseModel
from bank_agent.domain.access import AuthLevel, Role
from bank_agent.domain.identifiers import ChallengeId, PersonaId
from bank_agent.domain.identity import OtpPurpose
from bank_agent.domain.locale import Language

OneTimeCode = Annotated[str, StringConstraints(pattern=r"^[0-9]{6}$")]


class PersonaLogin(RequestModel):
    kind: Literal["persona"]
    persona_id: PersonaId


class DocumentLogin(RequestModel):
    """A document number plus the last four phone digits. Never proof of identity: it only opens a challenge."""

    kind: Literal["document"]
    document_number: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9-]{4,20}$")] = Field(repr=False)
    phone_last4: Annotated[str, StringConstraints(pattern=r"^[0-9]{4}$")] = Field(repr=False)


StartLoginRequest = Annotated[PersonaLogin | DocumentLogin, Field(discriminator="kind")]


class VerifyLoginRequest(RequestModel):
    challenge_id: ChallengeId
    code: OneTimeCode = Field(repr=False)
    language: Language | None = None


class VerifyStepUpRequest(RequestModel):
    challenge_id: ChallengeId
    code: OneTimeCode = Field(repr=False)


class ChallengeResponse(ResponseModel):
    """An open one-time-code challenge. ``demo_code`` is set only when demo mode is on, labeled as a demo."""

    challenge_id: ChallengeId
    purpose: OtpPurpose
    expires_at: datetime
    attempts_remaining: int
    delivery_channel: Literal["demo", "sms"]
    demo_code: OneTimeCode | None = None


class CsrfResponse(ResponseModel):
    """The double-submit token, also set as the readable CSRF cookie. Send it in ``X-CSRF-Token``."""

    csrf_token: Annotated[str, StringConstraints(max_length=128)]


class SessionView(ResponseModel):
    role: Role
    auth_level: AuthLevel
    step_up_valid: bool
    step_up_expires_at: datetime | None
    idle_expires_at: datetime
    absolute_expires_at: datetime
    language_preference: Language | None


class SignedInResponse(ResponseModel):
    """A new session: the session cookie is set, and ``csrf_token`` is the rotated double-submit token."""

    session: SessionView
    csrf_token: Annotated[str, StringConstraints(max_length=128)]
