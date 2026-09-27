"""Storage behind the mock identity provider: the directory lookup and the challenge table.

``ChallengeStore`` is internal to this adapter. ``InMemoryChallengeStore`` backs unit tests; the PostgreSQL
implementation lives in ``adapters/persistence/postgres/challenges.py``.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Protocol

from bank_agent.domain.identity import OtpPurpose


@dataclass(frozen=True)
class Subject:
    """Who a challenge is for: exactly one of a customer or a staff member."""

    customer_id: str | None = None
    staff_id: str | None = None
    staff_role: str | None = None
    """``agent`` or ``evaluator`` for a staff member."""


@dataclass(frozen=True)
class ChallengeRecord:
    challenge_id: str
    purpose: OtpPurpose
    subject_key: str
    subject: Subject | None
    session_id: str | None
    code_hash: str
    salt: str
    attempts: int
    max_attempts: int
    created_at: datetime
    expires_at: datetime
    consumed_at: datetime | None = None
    locked_until: datetime | None = None


class ChallengeStore(Protocol):
    async def find_persona(self, persona_id: str) -> Subject | None: ...

    async def find_document(self, document_lookup: str) -> tuple[str, str] | None:
        """Return ``(customer_id, phone_last4_lookup)`` for a document digest, if any."""
        ...

    async def locked_until(self, subject_key: str, now: datetime) -> datetime | None:
        """The latest lockout end for the subject that is still in the future, if any."""
        ...

    async def create(self, record: ChallengeRecord) -> None: ...

    async def get(self, challenge_id: str) -> ChallengeRecord | None: ...

    async def save(self, record: ChallengeRecord) -> None:
        """Store the attempts, consumption, and lockout of an existing challenge."""
        ...


class InMemoryChallengeStore:
    """Implements ``ChallengeStore`` over dictionaries, for unit tests."""

    def __init__(
        self,
        personas: dict[str, Subject] | None = None,
        documents: dict[str, tuple[str, str]] | None = None,
    ) -> None:
        self._personas = dict(personas or {})
        self._documents = dict(documents or {})
        self._challenges: dict[str, ChallengeRecord] = {}

    async def find_persona(self, persona_id: str) -> Subject | None:
        return self._personas.get(persona_id)

    async def find_document(self, document_lookup: str) -> tuple[str, str] | None:
        return self._documents.get(document_lookup)

    async def locked_until(self, subject_key: str, now: datetime) -> datetime | None:
        ends = [
            record.locked_until
            for record in self._challenges.values()
            if record.subject_key == subject_key and record.locked_until is not None and record.locked_until > now
        ]
        return max(ends, default=None)

    async def create(self, record: ChallengeRecord) -> None:
        if record.challenge_id in self._challenges:
            raise ValueError("a challenge with this id already exists")
        self._challenges[record.challenge_id] = record

    async def get(self, challenge_id: str) -> ChallengeRecord | None:
        return self._challenges.get(challenge_id)

    async def save(self, record: ChallengeRecord) -> None:
        current = self._challenges.get(record.challenge_id)
        if current is None:
            raise KeyError(record.challenge_id)
        self._challenges[record.challenge_id] = replace(
            current, attempts=record.attempts, consumed_at=record.consumed_at, locked_until=record.locked_until
        )
