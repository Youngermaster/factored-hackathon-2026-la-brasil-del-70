"""Retention periods and what one purge removed (``docs/security/data-retention.md``).

Pure values: the purge adapter turns a policy into cutoffs at a given instant and reports counts per table, never the
content of a row.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

RATE_LIMIT_WINDOW_RETENTION = timedelta(hours=1)
"""Rate-limit windows matter for two minutes; an hour leaves room for clock skew between workers."""


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    conversation_days: int
    session_days: int
    credit_application_days: int

    def __post_init__(self) -> None:
        if min(self.conversation_days, self.session_days, self.credit_application_days) < 1:
            raise ValueError("every retention period is at least one day")

    def cutoffs(self, now: datetime) -> "RetentionCutoffs":
        if now.tzinfo is None:
            raise ValueError("the purge instant must be timezone-aware")
        return RetentionCutoffs(
            conversations=now - timedelta(days=self.conversation_days),
            sessions=now - timedelta(days=self.session_days),
            credit_applications=now - timedelta(days=self.credit_application_days),
            rate_limit_windows=now - RATE_LIMIT_WINDOW_RETENTION,
        )


@dataclass(frozen=True, slots=True)
class RetentionCutoffs:
    """Rows that ended (or were last active) strictly before these instants are deleted."""

    conversations: datetime
    sessions: datetime
    credit_applications: datetime
    rate_limit_windows: datetime


@dataclass(frozen=True, slots=True)
class PurgeReport:
    """Rows deleted per table (or that would be, in a dry run)."""

    messages: int = 0
    turns: int = 0
    conversations: int = 0
    otp_challenges: int = 0
    sessions: int = 0
    trust_events: int = 0
    credit_applications: int = 0
    rate_limit_windows: int = 0
    dry_run: bool = False

    def counts(self) -> dict[str, int]:
        return {
            "messages": self.messages,
            "turns": self.turns,
            "conversations": self.conversations,
            "otp_challenges": self.otp_challenges,
            "sessions": self.sessions,
            "trust_events": self.trust_events,
            "credit_applications": self.credit_applications,
            "rate_limit_windows": self.rate_limit_windows,
        }

    @property
    def total(self) -> int:
        return sum(self.counts().values())
