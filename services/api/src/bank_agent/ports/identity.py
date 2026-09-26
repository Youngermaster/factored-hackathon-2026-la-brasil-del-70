"""Identity ports: the trusted test identity provider and the one-time-code sender (phase 05)."""

from datetime import datetime
from typing import Protocol

from bank_agent.domain.identifiers import ChallengeId
from bank_agent.domain.identity import (
    DocumentIdentification,
    OtpChallenge,
    OtpDeliveryReceipt,
    OtpDispatch,
    PersonaIdentification,
    VerifiedIdentity,
)
from bank_agent.domain.session import Session


class IdentityProvider(Protocol):
    """Verifies who a person is with a one-time code. Identification alone never grants access.

    Preconditions: codes are the six digits the person typed.
    Postconditions: ``verify`` returns an identity at exactly ``otp_verified``; ``verify_step_up`` returns the
    end of a step-up window. Codes are single use.
    Errors: an unknown person and a wrong code raise the same ``IdentityChallengeFailedError`` with the same
    message, so existence is never revealed; ``IdentityChallengeExpiredError`` after expiry;
    ``IdentityLockedError`` after too many attempts, with the cooldown.
    Isolation: the provider never returns personal data beyond the verified subject's identifiers.
    """

    async def start(self, identification: PersonaIdentification | DocumentIdentification) -> OtpChallenge:
        """Open a login challenge. Returns a challenge even for an unknown person, which then always fails."""
        ...

    async def verify(self, challenge_id: ChallengeId, code: str) -> VerifiedIdentity:
        """Check a login code."""
        ...

    async def start_step_up(self, session: Session) -> OtpChallenge:
        """Open a step-up challenge for the session's subject."""
        ...

    async def verify_step_up(self, session: Session, challenge_id: ChallengeId, code: str) -> datetime:
        """Check a step-up code and return when the step-up window closes."""
        ...


class OtpSender(Protocol):
    """Delivers one-time codes.

    Postconditions: the receipt carries the code only when demo mode is on (the demo sender); otherwise it
    only confirms delivery.
    Errors: ``ToolTransientError`` or ``ToolPermanentError`` when delivery fails.
    Isolation: the sender resolves the destination from the recipient id; codes are never logged.
    """

    async def send(self, dispatch: OtpDispatch) -> OtpDeliveryReceipt:
        """Deliver the code in ``dispatch``."""
        ...
