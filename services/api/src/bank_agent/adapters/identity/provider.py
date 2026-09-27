"""``MockIdentityProvider``: a trusted test identity service. Identification alone never grants access.

An identification that matches nobody still gets a challenge and a receipt of the same shape; its code can never
succeed, it counts toward the same lockout, and it fails with the same error as a wrong code, so the service
never reveals whether a customer exists.
"""

from dataclasses import replace
from datetime import datetime
from typing import Protocol

from bank_agent.adapters.identity.codes import IdentityKeys, generate_code, new_salt
from bank_agent.adapters.identity.store import ChallengeRecord, ChallengeStore, Subject
from bank_agent.application.identity.policy import OTP_POLICY, SESSION_POLICY, OtpPolicy, SessionPolicy
from bank_agent.domain.access import AuthLevel, Role
from bank_agent.domain.errors import IdentityChallengeExpiredError, IdentityChallengeFailedError, IdentityLockedError
from bank_agent.domain.identifiers import ChallengeId, CustomerId, IdKind, StaffId
from bank_agent.domain.identity import (
    DocumentIdentification,
    OtpChallenge,
    OtpDeliveryReceipt,
    OtpDispatch,
    OtpPurpose,
    PersonaIdentification,
    VerifiedIdentity,
)
from bank_agent.domain.session import Session
from bank_agent.ports.determinism import Clock, IdGenerator
from bank_agent.ports.identity import OtpSender


class DecoySender(OtpSender, Protocol):
    def decoy_receipt(self, challenge_id: str, code: str) -> OtpDeliveryReceipt: ...


class MockIdentityProvider:
    """Implements ``IdentityProvider``."""

    def __init__(
        self,
        *,
        store: ChallengeStore,
        sender: DecoySender,
        keys: IdentityKeys,
        clock: Clock,
        ids: IdGenerator,
        otp_policy: OtpPolicy = OTP_POLICY,
        session_policy: SessionPolicy = SESSION_POLICY,
    ) -> None:
        self._store, self._sender, self._keys = store, sender, keys
        self._clock, self._ids = clock, ids
        self._otp, self._session = otp_policy, session_policy

    async def _resolve(
        self, identification: PersonaIdentification | DocumentIdentification
    ) -> tuple[str, Subject | None]:
        if isinstance(identification, PersonaIdentification):
            key = self._keys.subject_key("persona", identification.persona_id)
            return key, await self._store.find_persona(identification.persona_id)
        lookup = self._keys.document_lookup(identification.document_number)
        found = await self._store.find_document(lookup)
        subject: Subject | None = None
        if found is not None:
            customer_id, phone_lookup = found
            if self._keys.phone_matches(customer_id, identification.phone_last4, phone_lookup):
                subject = Subject(customer_id=customer_id)
        return self._keys.subject_key("document", lookup), subject

    async def _refuse_if_locked(self, subject_key: str, now: datetime) -> None:
        locked_until = await self._store.locked_until(subject_key, now)
        if locked_until is not None:
            raise IdentityLockedError(locked_until - now)

    async def _open(
        self, purpose: OtpPurpose, subject_key: str, subject: Subject | None, session_id: str | None
    ) -> OtpChallenge:
        now = self._clock.now()
        await self._refuse_if_locked(subject_key, now)
        challenge_id = ChallengeId(self._ids.new(IdKind.CHALLENGE))
        code, salt = generate_code(), new_salt()
        record = ChallengeRecord(
            challenge_id=challenge_id,
            purpose=purpose,
            subject_key=subject_key,
            subject=subject,
            session_id=session_id,
            code_hash=self._keys.code_hash(salt=salt, challenge_id=challenge_id, code=code),
            salt=salt,
            attempts=0,
            max_attempts=self._otp.max_attempts,
            created_at=now,
            expires_at=now + self._otp.code_lifetime,
        )
        await self._store.create(record)
        if subject is None:
            receipt = self._sender.decoy_receipt(challenge_id, code)
        else:
            receipt = await self._sender.send(
                OtpDispatch(
                    challenge_id=challenge_id,
                    purpose=purpose,
                    recipient_customer_id=CustomerId(subject.customer_id) if subject.customer_id else None,
                    recipient_staff_id=StaffId(subject.staff_id) if subject.staff_id else None,
                    code=code,
                    expires_at=record.expires_at,
                )
            )
        return OtpChallenge(
            challenge_id=challenge_id,
            purpose=purpose,
            expires_at=record.expires_at,
            attempts_remaining=record.max_attempts,
            delivery=receipt,
        )

    async def _check(self, record: ChallengeRecord | None, code: str, purpose: OtpPurpose) -> ChallengeRecord:
        """Verify ``code`` against the record; count failures, lock after the last attempt, consume on success."""
        now = self._clock.now()
        if record is None or record.purpose is not purpose or record.consumed_at is not None:
            raise IdentityChallengeFailedError()
        await self._refuse_if_locked(record.subject_key, now)
        if record.attempts >= record.max_attempts:
            raise IdentityChallengeFailedError()
        if now >= record.expires_at:
            raise IdentityChallengeExpiredError()
        valid = self._keys.code_matches(
            expected_hash=record.code_hash, salt=record.salt, challenge_id=record.challenge_id, code=code
        )
        if not valid or record.subject is None:
            attempts = record.attempts + 1
            exhausted = attempts >= record.max_attempts
            locked_until = now + self._otp.lockout_cooldown if exhausted else None
            await self._store.save(replace(record, attempts=attempts, locked_until=locked_until))
            if exhausted:
                raise IdentityLockedError(self._otp.lockout_cooldown)
            raise IdentityChallengeFailedError()
        consumed = replace(record, consumed_at=now)
        await self._store.save(consumed)
        return consumed

    async def start(self, identification: PersonaIdentification | DocumentIdentification) -> OtpChallenge:
        subject_key, subject = await self._resolve(identification)
        return await self._open(OtpPurpose.LOGIN, subject_key, subject, None)

    async def verify(self, challenge_id: ChallengeId, code: str) -> VerifiedIdentity:
        record = await self._check(await self._store.get(challenge_id), code, OtpPurpose.LOGIN)
        subject = record.subject
        if subject is None or (subject.customer_id is None and subject.staff_role is None):
            raise IdentityChallengeFailedError()
        role = Role.CUSTOMER if subject.customer_id is not None else Role(str(subject.staff_role))
        return VerifiedIdentity(
            role=role,
            customer_id=CustomerId(subject.customer_id) if subject.customer_id else None,
            staff_id=StaffId(subject.staff_id) if subject.staff_id else None,
            auth_level=AuthLevel.OTP_VERIFIED,
            verified_at=self._clock.now(),
        )

    async def start_step_up(self, session: Session) -> OtpChallenge:
        subject = Subject(customer_id=session.customer_id, staff_id=session.staff_id, staff_role=_staff_role(session))
        subject_value = session.customer_id or session.staff_id or ""
        subject_key = self._keys.subject_key(f"session-{session.role.value}", subject_value)
        return await self._open(OtpPurpose.STEP_UP, subject_key, subject, session.session_id)

    async def verify_step_up(self, session: Session, challenge_id: ChallengeId, code: str) -> datetime:
        record = await self._store.get(challenge_id)
        if record is not None and record.session_id != session.session_id:
            record = None
        await self._check(record, code, OtpPurpose.STEP_UP)
        return self._clock.now() + self._session.step_up_window


def _staff_role(session: Session) -> str | None:
    return None if session.role is Role.CUSTOMER else session.role.value
