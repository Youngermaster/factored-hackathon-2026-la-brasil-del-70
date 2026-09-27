"""The session context every tool call runs under, and the tool settings the composition root supplies."""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from bank_agent.domain.access import AccessContext
from bank_agent.domain.accounts import CreditBalanceConvention
from bank_agent.domain.errors import SessionExpiredError, SessionRevokedError
from bank_agent.domain.locale import Country
from bank_agent.domain.session import ExpiryReason, Session
from bank_agent.ports.determinism import Clock

DEFAULT_MAX_STATEMENT_DAYS = 92
"""A safe cap on statement periods until the policy pack supplies the parameter (phase 06)."""
DEFAULT_DISPUTE_SLA = timedelta(days=15)
"""The dispute resolution target recorded on new cases until the policy pack supplies it (phase 06)."""


@dataclass(frozen=True)
class SessionContext:
    """A validated session at one instant. Tools take every customer identifier from here, never from arguments."""

    session: Session
    at: datetime

    @classmethod
    def of(cls, session: Session, clock: Clock) -> "SessionContext":
        """Refuse an expired or revoked session; tools never run on one."""
        now = clock.now()
        reason = session.expiry_reason(now)
        if reason is ExpiryReason.REVOKED:
            raise SessionRevokedError()
        if reason is ExpiryReason.ABSOLUTE:
            raise SessionExpiredError("absolute")
        if reason is ExpiryReason.IDLE:
            raise SessionExpiredError("idle")
        return cls(session=session, at=now)

    @property
    def access(self) -> AccessContext:
        return self.session.access_context()

    @property
    def actor_ref(self) -> str | None:
        return self.session.customer_id or self.session.staff_id

    @property
    def step_up_valid(self) -> bool:
        return self.session.step_up_valid(self.at)


@dataclass(frozen=True)
class ToolSettings:
    balance_convention: CreditBalanceConvention | None = None
    """The dataset's credit balance convention, so balances can show available credit on credit cards."""
    max_statement_days: int = DEFAULT_MAX_STATEMENT_DAYS
    dispute_sla: timedelta = DEFAULT_DISPUTE_SLA
    time_zones: dict[Country, ZoneInfo] = field(default_factory=dict)

    def zone(self, country: Country) -> ZoneInfo:
        return self.time_zones.get(country) or ZoneInfo(country.timezone_name)

    def local_date(self, country: Country, instant: datetime) -> date:
        return instant.astimezone(self.zone(country)).date()
