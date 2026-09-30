"""Session store port, including the trust state keyed by session lineage."""

from datetime import datetime
from typing import Protocol

from bank_agent.domain.identifiers import LineageId, SessionId
from bank_agent.domain.session import Session, TokenDigest
from bank_agent.domain.trust import TrustEvent, TrustState


class SessionStore(Protocol):
    """Stores server-side sessions and the append-only trust state of each session lineage.

    The store is not bound to an access context: sessions are looked up before any customer is known.
    Preconditions: callers pass a digest of the session token, never the token itself.
    Postconditions: ``get_by_token_digest`` returns only sessions whose digest matches; after ``rotate`` the
    old digest no longer resolves and the old session is revoked at the new session's creation time.
    Trust events are written outside any unit of work on purpose, so risk evidence survives a failed turn.
    Errors: ``create`` raises ``DuplicateEntityError`` for an existing session id or digest; ``save`` and
    ``rotate`` raise ``SessionNotFoundError`` for an unknown session and ``InvariantViolationError`` when the
    lineage or subject would change; ``append_trust_event`` raises ``TrustStateViolationError`` for an event
    older than the last one.
    Isolation: the raw token never reaches the store, and a digest resolves at most one session.
    """

    async def create(self, session: Session, token_digest: TokenDigest) -> None:
        """Store a new session under ``token_digest``."""
        ...

    async def get(self, session_id: SessionId) -> Session | None:
        """Return the session by its internal id."""
        ...

    async def get_by_token_digest(self, token_digest: TokenDigest) -> Session | None:
        """Return the session whose token has this digest, or ``None``."""
        ...

    async def save(self, session: Session) -> None:
        """Replace a stored session (after ``touched``, ``with_step_up``, or ``revoked``)."""
        ...

    async def rotate(self, old_session_id: SessionId, new_session: Session, new_token_digest: TokenDigest) -> None:
        """Replace a session with a new one in the same lineage, for example on a privilege change."""
        ...

    async def count_active(self, now: datetime) -> int:
        """How many sessions are live at ``now``: not revoked, before their absolute expiry, and seen within their
        idle timeout. Shared by every API process, so it is the deployment-wide count (an aggregate, no ids)."""
        ...

    async def append_trust_event(self, lineage_id: LineageId, event: TrustEvent) -> TrustState:
        """Append risk evidence to the lineage and return the new state."""
        ...

    async def get_trust_state(self, lineage_id: LineageId) -> TrustState:
        """Return the lineage's trust state; empty when nothing was recorded."""
        ...
