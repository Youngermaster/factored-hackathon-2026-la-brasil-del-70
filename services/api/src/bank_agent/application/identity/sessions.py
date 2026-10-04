"""Login, step-up, session resolution, and logout.

A session token is 256 random bits from ``secrets``, returned to the caller exactly once; the store keeps only its
SHA-256 digest. A step-up rotates the session (a privilege change): a new id and token in the same lineage, and
the old token stops resolving. Every outcome is written to the standalone audit log without identifiers or codes.
"""

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass

from bank_agent.application.identity.policy import SESSION_POLICY, SessionPolicy
from bank_agent.domain.access import AuthLevel
from bank_agent.domain.audit import AuditEvent, AuditOutcome
from bank_agent.domain.errors import AuthenticationError, SessionNotFoundError
from bank_agent.domain.identifiers import AuditEventId, ChallengeId, IdKind, LineageId, SessionId
from bank_agent.domain.identity import DocumentIdentification, OtpChallenge, PersonaIdentification
from bank_agent.domain.locale import Language
from bank_agent.domain.session import Session, TokenDigest
from bank_agent.ports.audit import AuditLog
from bank_agent.ports.determinism import Clock, IdGenerator
from bank_agent.ports.identity import IdentityProvider
from bank_agent.ports.sessions import SessionStore

TOKEN_BYTES = 32


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def token_digest(token: str) -> TokenDigest:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IssuedSession:
    """A session and its token. The token exists only here, on its way to the client."""

    session: Session
    token: str

    def __repr__(self) -> str:
        return f"IssuedSession(session_id={self.session.session_id!r}, token=<redacted>)"


class SessionService:
    def __init__(
        self,
        *,
        identity: IdentityProvider,
        store: SessionStore,
        audit: AuditLog,
        clock: Clock,
        ids: IdGenerator,
        policy: SessionPolicy = SESSION_POLICY,
        token_factory: Callable[[], str] = new_token,
    ) -> None:
        self._identity, self._store, self._audit = identity, store, audit
        self._clock, self._ids, self._policy = clock, ids, policy
        self._new_token = token_factory

    async def _record(self, action: str, outcome: AuditOutcome, session: Session | None = None) -> None:
        await self._audit.append(
            AuditEvent(
                event_id=AuditEventId(self._ids.new(IdKind.AUDIT_EVENT)),
                occurred_at=self._clock.now(),
                actor_role=session.role if session is not None else None,
                actor_ref=(session.customer_id or session.staff_id) if session is not None else None,
                action=action,
                outcome=outcome,
                arguments={"session_id": session.session_id} if session is not None else {},
            )
        )

    async def start_login(self, identification: PersonaIdentification | DocumentIdentification) -> OtpChallenge:
        try:
            challenge = await self._identity.start(identification)
        except AuthenticationError:
            await self._record("login_started", AuditOutcome.DENIED)
            raise
        await self._record("login_started", AuditOutcome.SUCCESS)
        return challenge

    async def complete_login(
        self, challenge_id: ChallengeId, code: str, language: Language | None = None
    ) -> IssuedSession:
        try:
            identity = await self._identity.verify(challenge_id, code)
        except AuthenticationError:
            await self._record("login_verified", AuditOutcome.FAILURE)
            raise
        now = self._clock.now()
        session_id = SessionId(self._ids.new(IdKind.SESSION))
        session = Session(
            session_id=session_id,
            lineage_id=LineageId(self._ids.new(IdKind.LINEAGE)),
            role=identity.role,
            customer_id=identity.customer_id,
            staff_id=identity.staff_id,
            auth_level=AuthLevel.OTP_VERIFIED,
            created_at=now,
            last_seen_at=now,
            idle_timeout=self._policy.idle_timeout,
            absolute_expires_at=now + self._policy.absolute_lifetime,
            language_preference=language,
        )
        token = self._new_token()
        await self._store.create(session, token_digest(token))
        await self._record("login_verified", AuditOutcome.SUCCESS, session)
        return IssuedSession(session=session, token=token)

    async def _current(self, token: str) -> Session:
        session = await self._store.get_by_token_digest(token_digest(token))
        if session is None:
            raise SessionNotFoundError()
        return session

    async def count_active(self) -> int:
        """Live sessions across every API process now (an aggregate for the active-session gauge)."""
        return await self._store.count_active(self._clock.now())

    async def resolve(self, token: str) -> Session:
        """Return the live session for ``token`` and record the activity (sliding the idle expiry).

        Raises ``SessionNotFoundError`` for an unknown token, ``SessionExpiredError`` (idle or absolute), or
        ``SessionRevokedError``.
        """
        touched = (await self._current(token)).touched(self._clock.now())
        await self._store.save(touched)
        return touched

    async def start_step_up(self, token: str) -> OtpChallenge:
        session = await self.resolve(token)
        challenge = await self._identity.start_step_up(session)
        await self._record("step_up_started", AuditOutcome.SUCCESS, session)
        return challenge

    async def complete_step_up(self, token: str, challenge_id: ChallengeId, code: str) -> IssuedSession:
        session = await self.resolve(token)
        try:
            until = await self._identity.verify_step_up(session, challenge_id, code)
        except AuthenticationError:
            await self._record("step_up_verified", AuditOutcome.FAILURE, session)
            raise
        now = self._clock.now()
        rotated = session.evolve(
            session_id=SessionId(self._ids.new(IdKind.SESSION)), created_at=now, last_seen_at=now
        ).with_step_up(now=now, until=until)
        new_token = self._new_token()
        await self._store.rotate(session.session_id, rotated, token_digest(new_token))
        await self._record("step_up_verified", AuditOutcome.SUCCESS, rotated)
        return IssuedSession(session=rotated, token=new_token)

    async def logout(self, token: str) -> None:
        session = await self._current(token)
        await self._store.save(session.revoked(self._clock.now()))
        await self._record("logout", AuditOutcome.SUCCESS, session)

    async def revoke(self, session_id: SessionId) -> None:
        session = await self._store.get(session_id)
        if session is None:
            raise SessionNotFoundError()
        await self._store.save(session.revoked(self._clock.now()))
        await self._record("session_revoked", AuditOutcome.SUCCESS, session)
