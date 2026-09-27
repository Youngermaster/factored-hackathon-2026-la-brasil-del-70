"""PostgreSQL storage for the mock identity provider, under the ``identity`` database role.

The directory holds keyed digests only (``identity_directory``, ``staff_members``); challenges hold the code
hash and salt, never the code.
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncEngine

from bank_agent.adapters.identity.store import ChallengeRecord, Subject
from bank_agent.adapters.persistence.postgres.database import DatabaseRole, open_transaction
from bank_agent.adapters.persistence.postgres.transaction import Row, Tx
from bank_agent.domain.identity import OtpPurpose

_INSERT = (
    "INSERT INTO app.otp_challenges (challenge_id, purpose, subject_key, customer_id, staff_id, session_id, "
    "code_hash, salt, attempts, max_attempts, created_at, expires_at, consumed_at, locked_until) VALUES "
    "(:challenge_id, :purpose, :subject_key, :customer_id, :staff_id, :session_id, :code_hash, :salt, :attempts, "
    ":max_attempts, :created_at, :expires_at, :consumed_at, :locked_until)"
)


def _record(row: Row) -> ChallengeRecord:
    customer, staff = row["customer_id"], row["staff_id"]
    subject = None
    if customer is not None or staff is not None:
        subject = Subject(customer_id=customer, staff_id=staff, staff_role=row["staff_role"])
    return ChallengeRecord(
        challenge_id=row["challenge_id"],
        purpose=OtpPurpose(row["purpose"]),
        subject_key=row["subject_key"],
        subject=subject,
        session_id=row["session_id"],
        code_hash=row["code_hash"],
        salt=row["salt"],
        attempts=row["attempts"],
        max_attempts=row["max_attempts"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        consumed_at=row["consumed_at"],
        locked_until=row["locked_until"],
    )


class PostgresChallengeStore:
    """Implements the identity adapter's ``ChallengeStore``."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def find_persona(self, persona_id: str) -> Subject | None:
        async with open_transaction(self._engine, DatabaseRole.IDENTITY) as connection:
            tx = Tx(connection)
            row = await tx.one_or_none(
                "SELECT customer_id FROM app.identity_directory WHERE persona_id = :persona", {"persona": persona_id}
            )
            if row is not None:
                return Subject(customer_id=row["customer_id"])
            staff = await tx.one_or_none(
                "SELECT staff_id, role FROM app.staff_members WHERE persona_id = :persona", {"persona": persona_id}
            )
        return Subject(staff_id=staff["staff_id"], staff_role=staff["role"]) if staff is not None else None

    async def find_document(self, document_lookup: str) -> tuple[str, str] | None:
        async with open_transaction(self._engine, DatabaseRole.IDENTITY) as connection:
            row = await Tx(connection).one_or_none(
                "SELECT customer_id, phone_last4_lookup FROM app.identity_directory WHERE document_lookup = :lookup",
                {"lookup": document_lookup},
            )
        return (row["customer_id"], row["phone_last4_lookup"]) if row is not None else None

    async def locked_until(self, subject_key: str, now: datetime) -> datetime | None:
        async with open_transaction(self._engine, DatabaseRole.IDENTITY) as connection:
            value = await Tx(connection).scalar(
                "SELECT max(locked_until) FROM app.otp_challenges WHERE subject_key = :key AND locked_until > :now",
                {"key": subject_key, "now": now},
            )
        return value if isinstance(value, datetime) else None

    async def create(self, record: ChallengeRecord) -> None:
        subject = record.subject or Subject()
        async with open_transaction(self._engine, DatabaseRole.IDENTITY) as connection:
            await Tx(connection).execute(
                _INSERT,
                {
                    "challenge_id": record.challenge_id,
                    "purpose": record.purpose.value,
                    "subject_key": record.subject_key,
                    "customer_id": subject.customer_id,
                    "staff_id": subject.staff_id,
                    "session_id": record.session_id,
                    "code_hash": record.code_hash,
                    "salt": record.salt,
                    "attempts": record.attempts,
                    "max_attempts": record.max_attempts,
                    "created_at": record.created_at,
                    "expires_at": record.expires_at,
                    "consumed_at": record.consumed_at,
                    "locked_until": record.locked_until,
                },
            )

    async def get(self, challenge_id: str) -> ChallengeRecord | None:
        async with open_transaction(self._engine, DatabaseRole.IDENTITY) as connection:
            row = await Tx(connection).one_or_none(
                "SELECT c.*, s.role AS staff_role FROM app.otp_challenges c "
                "LEFT JOIN app.staff_members s ON s.staff_id = c.staff_id WHERE c.challenge_id = :id",
                {"id": challenge_id},
            )
        return _record(row) if row is not None else None

    async def save(self, record: ChallengeRecord) -> None:
        async with open_transaction(self._engine, DatabaseRole.IDENTITY) as connection:
            changed = await Tx(connection).execute(
                "UPDATE app.otp_challenges SET attempts = :attempts, consumed_at = :consumed_at, "
                "locked_until = :locked_until WHERE challenge_id = :id",
                {
                    "attempts": record.attempts,
                    "consumed_at": record.consumed_at,
                    "locked_until": record.locked_until,
                    "id": record.challenge_id,
                },
            )
        if changed != 1:
            raise KeyError(record.challenge_id)
