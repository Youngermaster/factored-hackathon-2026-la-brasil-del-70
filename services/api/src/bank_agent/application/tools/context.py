"""The session context every tool call runs under, and the tool settings the composition root supplies.

Policy values the tools enforce (the statement period cap, the dispute resolution target per country, and which
writes need step-up) come from the policy pack through ``ToolPolicy``; the tools hold no policy defaults.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from bank_agent.domain.access import AccessContext
from bank_agent.domain.accounts import CreditBalanceConvention
from bank_agent.domain.actions import ActionKind
from bank_agent.domain.errors import PolicyPackInvalidError, SessionExpiredError, SessionRevokedError
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.policy import Jurisdiction
from bank_agent.domain.session import ExpiryReason, Session
from bank_agent.ports.determinism import Clock
from bank_agent.ports.policy import PolicyRepository

STATEMENT_DAYS_PARAM = "max_statement_days"
DISPUTE_SLA_PARAM = "resolution_sla_days"


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


def _param(policy: PolicyRepository, name: str, jurisdiction: Jurisdiction) -> int:
    """The integer parameter ``name`` of the one current clause of ``jurisdiction`` that declares it."""
    values = [
        clause.metadata.params[name]
        for clause in policy.list_clauses(language=Language.ES)
        if clause.metadata.jurisdiction is jurisdiction and name in clause.metadata.params
    ]
    if len(values) != 1 or not isinstance(values[0], int) or isinstance(values[0], bool):
        raise PolicyPackInvalidError(f"exactly one {jurisdiction.value} clause must declare {name} as an integer")
    return values[0]


@dataclass(frozen=True)
class ToolPolicy:
    """Tool parameters from the policy pack, identified by ``pack_version``."""

    max_statement_days: int
    dispute_sla_days: Mapping[Country, int]
    step_up_actions: frozenset[ActionKind]
    pack_version: str

    def __post_init__(self) -> None:
        if ActionKind.BLOCK_CARD not in self.step_up_actions:
            raise PolicyPackInvalidError("a protective card block always requires step-up")
        if set(self.dispute_sla_days) != set(Country):
            raise PolicyPackInvalidError("every jurisdiction needs a dispute resolution target")

    @classmethod
    def from_policy(cls, policy: PolicyRepository) -> "ToolPolicy":
        return cls(
            max_statement_days=_param(policy, STATEMENT_DAYS_PARAM, Jurisdiction.ALL),
            dispute_sla_days={c: _param(policy, DISPUTE_SLA_PARAM, Jurisdiction(c.value)) for c in Country},
            step_up_actions=frozenset(a for a in ActionKind if policy.action_requirements(a).requires_step_up),
            pack_version=policy.pack_version(),
        )

    def dispute_sla(self, country: Country) -> timedelta:
        return timedelta(days=self.dispute_sla_days[country])


@dataclass(frozen=True)
class ToolSettings:
    policy: ToolPolicy
    balance_convention: CreditBalanceConvention | None = None
    """The dataset's credit balance convention, so balances can show available credit on credit cards."""
    time_zones: dict[Country, ZoneInfo] = field(default_factory=dict)

    @property
    def max_statement_days(self) -> int:
        return self.policy.max_statement_days

    def zone(self, country: Country) -> ZoneInfo:
        return self.time_zones.get(country) or ZoneInfo(country.timezone_name)

    def local_date(self, country: Country, instant: datetime) -> date:
        return instant.astimezone(self.zone(country)).date()
