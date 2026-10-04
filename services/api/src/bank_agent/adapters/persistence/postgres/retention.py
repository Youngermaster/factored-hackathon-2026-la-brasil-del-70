"""``PostgresRetentionPurge``: deletes what the retention policy no longer allows, as the owner, in one transaction.

The owner sets ``app.role = 'retention'``; migration 0012 gives that context read and delete policies on exactly the
purged tables and lets the append-only triggers of ``messages`` and ``trust_events`` accept its deletes. Execution
records, audit events, handoffs, cases, and reference data are never touched. A dry run counts inside the same
transaction and rolls it back. The report holds counts only.
"""

from datetime import datetime
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from bank_agent.adapters.persistence.postgres.database import DatabaseRole, set_context
from bank_agent.domain.retention import PurgeReport, RetentionCutoffs, RetentionPolicy

_STALE_CONVERSATIONS: Final = """
    SELECT c.conversation_id FROM app.conversations c
    WHERE GREATEST(
        c.created_at,
        COALESCE(
            (SELECT max(t.received_at) FROM app.turns t WHERE t.conversation_id = c.conversation_id), c.created_at
        ),
        COALESCE((SELECT max(m.sent_at) FROM app.messages m WHERE m.conversation_id = c.conversation_id), c.created_at),
        COALESCE(
            (SELECT max(m.sent_at) FROM app.human_messages m WHERE m.conversation_id = c.conversation_id), c.created_at
        )
    ) < :cutoff
"""
_ENDED_SESSIONS: Final = """
    SELECT session_id FROM app.sessions
    WHERE LEAST(
        absolute_expires_at,
        COALESCE(revoked_at, absolute_expires_at),
        last_seen_at + idle_timeout_seconds * interval '1 second'
    ) < :cutoff
"""
_DELETES: Final = (
    ("messages", "DELETE FROM app.human_messages WHERE conversation_id = ANY(:conversations)"),
    ("messages", "DELETE FROM app.messages WHERE conversation_id = ANY(:conversations)"),
    ("turns", "DELETE FROM app.turns WHERE conversation_id = ANY(:conversations)"),
    ("conversations", "DELETE FROM app.conversations WHERE conversation_id = ANY(:conversations)"),
    (
        "otp_challenges",
        "DELETE FROM app.otp_challenges WHERE expires_at < :sessions_cutoff OR session_id = ANY(:sessions)",
    ),
    ("sessions", "DELETE FROM app.sessions WHERE session_id = ANY(:sessions)"),
    ("trust_events", "DELETE FROM app.trust_events WHERE occurred_at < :sessions_cutoff"),
    (
        "credit_applications",
        "DELETE FROM app.credit_applications WHERE status IN ('withdrawn', 'closed') "
        "AND (document ->> 'updated_at')::timestamptz < :credit_cutoff",
    ),
    ("rate_limit_windows", "DELETE FROM app.rate_limit_windows WHERE window_start < :windows_cutoff"),
)


class PostgresRetentionPurge:
    """Runs the purge over an owner-role engine."""

    def __init__(self, owner_engine: AsyncEngine) -> None:
        self._engine = owner_engine

    async def purge(self, policy: RetentionPolicy, now: datetime, *, dry_run: bool = False) -> PurgeReport:
        cutoffs = policy.cutoffs(now)
        async with self._engine.connect() as connection:
            transaction = await connection.begin()
            try:
                counts = await _delete(connection, cutoffs)
            except BaseException:
                await transaction.rollback()
                raise
            if dry_run:
                await transaction.rollback()
            else:
                await transaction.commit()
        return PurgeReport(**counts, dry_run=dry_run)


async def _ids(connection: AsyncConnection, statement: str, cutoff: datetime) -> list[str]:
    return [str(row[0]) for row in await connection.execute(text(statement), {"cutoff": cutoff})]


async def _delete(connection: AsyncConnection, cutoffs: RetentionCutoffs) -> dict[str, int]:
    await set_context(connection, DatabaseRole.RETENTION, None)
    values = {
        "conversations": await _ids(connection, _STALE_CONVERSATIONS, cutoffs.conversations),
        "sessions": await _ids(connection, _ENDED_SESSIONS, cutoffs.sessions),
        "sessions_cutoff": cutoffs.sessions,
        "credit_cutoff": cutoffs.credit_applications,
        "windows_cutoff": cutoffs.rate_limit_windows,
    }
    counts: dict[str, int] = {}
    for table, statement in _DELETES:
        result = await connection.execute(text(statement), values)
        counts[table] = counts.get(table, 0) + int(result.rowcount or 0)
    return counts
