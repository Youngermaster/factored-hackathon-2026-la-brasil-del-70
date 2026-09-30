"""PostgreSQL session store and trust state, under the ``identity`` database role.

Sessions are looked up before any customer is known, so this store is not bound to an access context; row-level
security admits it only with ``app.role = 'identity'``. Only token digests are stored.
"""

from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from bank_agent.adapters.persistence.postgres.database import DatabaseRole, open_transaction
from bank_agent.adapters.persistence.postgres.mappers.sessions import (
    session_from_row,
    session_to_row,
    trust_event_from_row,
    trust_event_to_row,
)
from bank_agent.adapters.persistence.postgres.transaction import Row, Tx
from bank_agent.domain.errors import (
    ConcurrencyConflictError,
    DuplicateEntityError,
    InvariantViolationError,
    SessionNotFoundError,
)
from bank_agent.domain.identifiers import LineageId, SessionId
from bank_agent.domain.session import Session, TokenDigest
from bank_agent.domain.trust import TrustEvent, TrustState

_INSERT = (
    "INSERT INTO app.sessions (session_id, token_digest, lineage_id, role, customer_id, staff_id, auth_level, "
    "created_at, last_seen_at, idle_timeout_seconds, absolute_expires_at, step_up_expires_at, revoked_at, "
    "language_preference) VALUES (:session_id, :token_digest, :lineage_id, :role, :customer_id, :staff_id, "
    ":auth_level, :created_at, :last_seen_at, :idle_timeout_seconds, :absolute_expires_at, :step_up_expires_at, "
    ":revoked_at, :language_preference)"
)
_SAVE = (
    "UPDATE app.sessions SET auth_level = :auth_level, last_seen_at = :last_seen_at, "
    "absolute_expires_at = :absolute_expires_at, step_up_expires_at = :step_up_expires_at, "
    "revoked_at = :revoked_at, language_preference = :language_preference, "
    "idle_timeout_seconds = :idle_timeout_seconds WHERE session_id = :session_id"
)


_COUNT_ACTIVE = (
    "SELECT count(*) FROM app.sessions WHERE (revoked_at IS NULL OR revoked_at > :now) "
    "AND absolute_expires_at > :now AND last_seen_at + idle_timeout_seconds * interval '1 second' > :now"
)


def _identity(session: Session) -> tuple[object, ...]:
    return (session.lineage_id, session.role, session.customer_id, session.staff_id)


class PostgresSessionStore:
    """Implements ``SessionStore``."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def _one(self, tx: Tx, where: str, value: str) -> Row | None:
        return await tx.one_or_none(f"SELECT * FROM app.sessions WHERE {where} = :value", {"value": value})  # noqa: S608  # nosec B608 (fixed column)

    async def create(self, session: Session, token_digest: TokenDigest) -> None:
        async with open_transaction(self._engine, DatabaseRole.IDENTITY) as connection:
            tx = Tx(connection)
            try:
                await tx.guarded(_INSERT, {**session_to_row(session), "token_digest": token_digest})
            except IntegrityError as error:
                raise DuplicateEntityError("the session id or token digest is already in use") from error

    async def get(self, session_id: SessionId) -> Session | None:
        async with open_transaction(self._engine, DatabaseRole.IDENTITY) as connection:
            row = await self._one(Tx(connection), "session_id", session_id)
        return session_from_row(row) if row is not None else None

    async def get_by_token_digest(self, token_digest: TokenDigest) -> Session | None:
        async with open_transaction(self._engine, DatabaseRole.IDENTITY) as connection:
            row = await self._one(Tx(connection), "token_digest", token_digest)
        return session_from_row(row) if row is not None else None

    async def save(self, session: Session) -> None:
        async with open_transaction(self._engine, DatabaseRole.IDENTITY) as connection:
            tx = Tx(connection)
            row = await self._one(tx, "session_id", session.session_id)
            if row is None:
                raise SessionNotFoundError()
            current = session_from_row(row)
            if _identity(current) != _identity(session) or current.created_at != session.created_at:
                raise InvariantViolationError("a session's lineage, subject, and creation time cannot change")
            await tx.execute(_SAVE, session_to_row(session))

    async def rotate(self, old_session_id: SessionId, new_session: Session, new_token_digest: TokenDigest) -> None:
        async with open_transaction(self._engine, DatabaseRole.IDENTITY) as connection:
            tx = Tx(connection)
            row = await self._one(tx, "session_id", old_session_id)
            if row is None:
                raise SessionNotFoundError()
            old = session_from_row(row)
            if _identity(old) != _identity(new_session):
                raise InvariantViolationError("a rotated session keeps its lineage and subject")
            try:
                await tx.guarded(_INSERT, {**session_to_row(new_session), "token_digest": new_token_digest})
            except IntegrityError as error:
                raise DuplicateEntityError("the session id or token digest is already in use") from error
            retired = session_to_row(old.revoked(new_session.created_at))
            await tx.execute(_SAVE, retired)
            await tx.execute(
                "UPDATE app.sessions SET token_digest = encode(sha256(convert_to('retired:' || session_id || "
                "':' || token_digest, 'UTF8')), 'hex') WHERE session_id = :session_id",
                {"session_id": old_session_id},
            )

    async def count_active(self, now: datetime) -> int:
        async with open_transaction(self._engine, DatabaseRole.IDENTITY) as connection:
            count = await Tx(connection).scalar(_COUNT_ACTIVE, {"now": now})
        return count if isinstance(count, int) else 0

    async def append_trust_event(self, lineage_id: LineageId, event: TrustEvent) -> TrustState:
        async with open_transaction(self._engine, DatabaseRole.IDENTITY) as connection:
            tx = Tx(connection)
            state = await self._trust_state(tx, lineage_id)
            updated = state.append(event)
            try:
                await tx.guarded(
                    "INSERT INTO app.trust_events (lineage_id, sequence, occurred_at, content_digest, document) "
                    "VALUES (:lineage_id, :sequence, :occurred_at, :content_digest, CAST(:document AS jsonb))",
                    trust_event_to_row(lineage_id, len(updated.events), event),
                )
            except IntegrityError as error:
                raise ConcurrencyConflictError("another trust event was appended concurrently") from error
        return updated

    async def get_trust_state(self, lineage_id: LineageId) -> TrustState:
        async with open_transaction(self._engine, DatabaseRole.IDENTITY) as connection:
            return await self._trust_state(Tx(connection), lineage_id)

    async def _trust_state(self, tx: Tx, lineage_id: LineageId) -> TrustState:
        rows = await tx.rows(
            "SELECT document FROM app.trust_events WHERE lineage_id = :lineage ORDER BY sequence",
            {"lineage": lineage_id},
        )
        return TrustState(lineage_id=lineage_id, events=tuple(trust_event_from_row(row) for row in rows))
