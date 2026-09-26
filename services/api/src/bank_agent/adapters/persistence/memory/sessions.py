"""In-memory session store with trust state per lineage."""

from bank_agent.domain.errors import DuplicateEntityError, InvariantViolationError, SessionNotFoundError
from bank_agent.domain.identifiers import LineageId, SessionId
from bank_agent.domain.session import Session, TokenDigest
from bank_agent.domain.trust import TrustEvent, TrustState


def _identity(session: Session) -> tuple[object, ...]:
    return (session.lineage_id, session.role, session.customer_id, session.staff_id)


class InMemorySessionStore:
    """Implements ``SessionStore``. Only token digests are kept; the store never sees a raw token."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._digests: dict[str, str] = {}
        self._trust: dict[str, TrustState] = {}

    async def create(self, session: Session, token_digest: TokenDigest) -> None:
        if session.session_id in self._sessions or token_digest in self._digests:
            raise DuplicateEntityError("the session id or token digest is already in use")
        self._sessions[session.session_id] = session
        self._digests[token_digest] = session.session_id

    async def get(self, session_id: SessionId) -> Session | None:
        return self._sessions.get(session_id)

    async def get_by_token_digest(self, token_digest: TokenDigest) -> Session | None:
        session_id = self._digests.get(token_digest)
        return self._sessions.get(session_id) if session_id is not None else None

    def _existing(self, session_id: SessionId) -> Session:
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError()
        return session

    async def save(self, session: Session) -> None:
        current = self._existing(session.session_id)
        if _identity(current) != _identity(session) or current.created_at != session.created_at:
            raise InvariantViolationError("a session's lineage, subject, and creation time cannot change")
        self._sessions[session.session_id] = session

    async def rotate(self, old_session_id: SessionId, new_session: Session, new_token_digest: TokenDigest) -> None:
        old = self._existing(old_session_id)
        if _identity(old) != _identity(new_session):
            raise InvariantViolationError("a rotated session keeps its lineage and subject")
        if new_session.session_id in self._sessions or new_token_digest in self._digests:
            raise DuplicateEntityError("the session id or token digest is already in use")
        self._sessions[old_session_id] = old.revoked(new_session.created_at)
        for digest in [digest for digest, session_id in self._digests.items() if session_id == old_session_id]:
            del self._digests[digest]
        self._sessions[new_session.session_id] = new_session
        self._digests[new_token_digest] = new_session.session_id

    async def append_trust_event(self, lineage_id: LineageId, event: TrustEvent) -> TrustState:
        state = self._trust.get(lineage_id) or TrustState.empty(lineage_id)
        updated = state.append(event)
        self._trust[lineage_id] = updated
        return updated

    async def get_trust_state(self, lineage_id: LineageId) -> TrustState:
        return self._trust.get(lineage_id) or TrustState.empty(lineage_id)
