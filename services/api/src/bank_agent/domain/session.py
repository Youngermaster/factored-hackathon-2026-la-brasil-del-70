"""Server-side sessions.

A session stores computed expiry instants rather than reading settings, so every expiry question is a pure
function of the session and an instant from the ``Clock`` port. A session expires exactly at its expiry
instant (``now >= expires_at``). Step-up is a time window on top of the base level, never a base level itself.
The raw session token never enters the domain: stores look sessions up by a token digest.
"""

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated, Self

from pydantic import AfterValidator, StringConstraints, model_validator

from bank_agent.domain.access import AccessContext, AuthLevel, Role, check_subject
from bank_agent.domain.base import DomainModel, UtcDatetime
from bank_agent.domain.errors import ClockRegressionError, SessionExpiredError, SessionRevokedError
from bank_agent.domain.identifiers import CustomerId, LineageId, SessionId, StaffId
from bank_agent.domain.locale import Language

TokenDigest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
"""A SHA-256 hex digest of a session token. Stores look sessions up by digest; the token never enters the domain."""


class ExpiryReason(StrEnum):
    IDLE = "idle"
    ABSOLUTE = "absolute"
    REVOKED = "revoked"


def _positive(value: timedelta) -> timedelta:
    if value <= timedelta(0):
        raise ValueError("a timeout must be positive")
    return value


class SessionSnapshot(DomainModel):
    """A session evaluated at one instant. The policy evaluator (phase 06) receives this, never a live session."""

    role: Role
    customer_id: CustomerId | None = None
    staff_id: StaffId | None = None
    effective_auth_level: AuthLevel
    step_up_valid: bool
    expired: bool
    expiry_reason: ExpiryReason | None = None
    at: UtcDatetime


class Session(DomainModel):
    session_id: SessionId
    lineage_id: LineageId
    role: Role
    customer_id: CustomerId | None = None
    staff_id: StaffId | None = None
    auth_level: AuthLevel
    created_at: UtcDatetime
    last_seen_at: UtcDatetime
    idle_timeout: Annotated[timedelta, AfterValidator(_positive)]
    absolute_expires_at: UtcDatetime
    step_up_expires_at: UtcDatetime | None = None
    revoked_at: UtcDatetime | None = None
    language_preference: Language | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        check_subject(self.role, self.customer_id, self.staff_id)
        if self.auth_level is AuthLevel.STEP_UP:
            raise ValueError("step-up is a time window, not a base authentication level")
        if self.last_seen_at < self.created_at or self.absolute_expires_at <= self.created_at:
            raise ValueError("session instants are out of order")
        return self

    @property
    def idle_expires_at(self) -> datetime:
        return min(self.last_seen_at + self.idle_timeout, self.absolute_expires_at)

    def expiry_reason(self, now: datetime) -> ExpiryReason | None:
        """Why the session is expired at ``now``, or ``None`` while it is valid."""
        if self.revoked_at is not None and now >= self.revoked_at:
            return ExpiryReason.REVOKED
        if now >= self.absolute_expires_at:
            return ExpiryReason.ABSOLUTE
        if now >= self.last_seen_at + self.idle_timeout:
            return ExpiryReason.IDLE
        return None

    def is_expired(self, now: datetime) -> bool:
        return self.expiry_reason(now) is not None

    def step_up_valid(self, now: datetime) -> bool:
        return not self.is_expired(now) and self.step_up_expires_at is not None and now < self.step_up_expires_at

    def effective_auth_level(self, now: datetime) -> AuthLevel:
        if self.is_expired(now):
            return AuthLevel.NONE
        if self.step_up_valid(now):
            return AuthLevel.STEP_UP
        return self.auth_level

    def _require_valid(self, now: datetime) -> None:
        if now < self.last_seen_at:
            raise ClockRegressionError("an instant earlier than the last activity")
        reason = self.expiry_reason(now)
        if reason is ExpiryReason.REVOKED:
            raise SessionRevokedError()
        if reason is ExpiryReason.ABSOLUTE:
            raise SessionExpiredError("absolute")
        if reason is ExpiryReason.IDLE:
            raise SessionExpiredError("idle")

    def touched(self, now: datetime) -> Self:
        """Record activity at ``now``. The idle expiry moves forward but never past the absolute expiry."""
        self._require_valid(now)
        return self.evolve(last_seen_at=now)

    def with_step_up(self, *, now: datetime, until: datetime) -> Self:
        """Open a step-up window ending at ``until``, capped at the absolute expiry."""
        self._require_valid(now)
        if until <= now:
            raise ValueError("a step-up window must end in the future")
        return self.evolve(last_seen_at=now, step_up_expires_at=min(until, self.absolute_expires_at))

    def revoked(self, at: datetime) -> Self:
        if self.revoked_at is not None:
            return self
        return self.evolve(revoked_at=at)

    def access_context(self) -> AccessContext:
        return AccessContext(
            role=self.role, customer_id=self.customer_id, staff_id=self.staff_id, session_id=self.session_id
        )

    def snapshot(self, now: datetime) -> SessionSnapshot:
        return SessionSnapshot(
            role=self.role,
            customer_id=self.customer_id,
            staff_id=self.staff_id,
            effective_auth_level=self.effective_auth_level(now),
            step_up_valid=self.step_up_valid(now),
            expired=self.is_expired(now),
            expiry_reason=self.expiry_reason(now),
            at=now,
        )
