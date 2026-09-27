"""Trust state: append-only risk evidence for a session lineage, with a risk tier that never decreases.

Each event kind has a fixed severity. The risk tier is the highest tier any rule below reaches:

- one medium event gives ``elevated``, one high event gives ``high``;
- two medium-or-higher events give ``high``;
- three low events give ``elevated``.

Every rule depends only on counts that can grow, so appending an event can never lower the tier; a Hypothesis
test proves it for arbitrary sequences. The state is keyed by the session lineage, which survives rotation and
re-authentication into the same conversation, so logging in again does not reset risk. See ADR 0005.
"""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import StringConstraints, model_validator

from bank_agent.domain.base import Code, DomainModel, UtcDatetime
from bank_agent.domain.errors import TrustStateViolationError
from bank_agent.domain.identifiers import LineageId, SourceRef, TurnId


class TrustEventKind(StrEnum):
    FAILED_OTP = "failed_otp"
    OTP_LOCKOUT = "otp_lockout"
    CROSS_CUSTOMER_PROBE = "cross_customer_probe"
    INJECTION_DETECTED = "injection_detected"
    THIRD_PARTY_ADMISSION = "third_party_admission"
    UNUSUAL_AMOUNT = "unusual_amount"
    IDENTITY_MISMATCH = "identity_mismatch"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskTier(StrEnum):
    LOW = "low"
    ELEVATED = "elevated"
    HIGH = "high"

    @property
    def rank(self) -> int:
        return _TIER_RANKS[self]


_TIER_RANKS = {RiskTier.LOW: 0, RiskTier.ELEVATED: 1, RiskTier.HIGH: 2}

SEVERITIES: dict[TrustEventKind, Severity] = {
    TrustEventKind.FAILED_OTP: Severity.LOW,
    TrustEventKind.UNUSUAL_AMOUNT: Severity.LOW,
    TrustEventKind.OTP_LOCKOUT: Severity.MEDIUM,
    TrustEventKind.INJECTION_DETECTED: Severity.MEDIUM,
    TrustEventKind.THIRD_PARTY_ADMISSION: Severity.MEDIUM,
    TrustEventKind.CROSS_CUSTOMER_PROBE: Severity.HIGH,
    TrustEventKind.IDENTITY_MISMATCH: Severity.HIGH,
}
_SEVERITY_TIERS = {Severity.LOW: RiskTier.LOW, Severity.MEDIUM: RiskTier.ELEVATED, Severity.HIGH: RiskTier.HIGH}
MEDIUM_OR_HIGHER_FOR_HIGH = 2
LOW_EVENTS_FOR_ELEVATED = 3

DetectorRef = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*:[a-z0-9_]+@[A-Za-z0-9._-]+$")]
"""The component that raised the event, for example ``injection:heuristic@1``."""


class TrustEvent(DomainModel):
    """One piece of risk evidence. It has no free-text field, so an attack payload is never copied into it."""

    kind: TrustEventKind
    occurred_at: UtcDatetime
    turn_id: TurnId | None = None
    detector: DetectorRef
    evidence: SourceRef | None = None
    detail_code: Code

    @property
    def severity(self) -> Severity:
        return SEVERITIES[self.kind]


def tier_for(events: tuple[TrustEvent, ...]) -> RiskTier:
    """The risk tier for a collection of events. Monotone: adding events never lowers the result."""
    tier = RiskTier.LOW
    medium_or_higher = 0
    low = 0
    for event in events:
        severity = event.severity
        candidate = _SEVERITY_TIERS[severity]
        if candidate.rank > tier.rank:
            tier = candidate
        if severity is Severity.LOW:
            low += 1
        else:
            medium_or_higher += 1
    if medium_or_higher >= MEDIUM_OR_HIGHER_FOR_HIGH:
        return RiskTier.HIGH
    if low >= LOW_EVENTS_FOR_ELEVATED and tier.rank < RiskTier.ELEVATED.rank:
        return RiskTier.ELEVATED
    return tier


class TrustState(DomainModel):
    lineage_id: LineageId
    events: tuple[TrustEvent, ...] = ()

    @model_validator(mode="after")
    def _validate_order(self) -> Self:
        for earlier, later in zip(self.events, self.events[1:], strict=False):
            if later.occurred_at < earlier.occurred_at:
                raise ValueError("trust events must be in chronological order")
        return self

    @classmethod
    def empty(cls, lineage_id: LineageId) -> Self:
        return cls(lineage_id=lineage_id)

    def append(self, event: TrustEvent) -> Self:
        """Return a new state with ``event`` appended. An event older than the last one raises."""
        if self.events and event.occurred_at < self.events[-1].occurred_at:
            raise TrustStateViolationError("trust events can only be appended in chronological order")
        return self.evolve(events=(*self.events, event))

    @property
    def risk_tier(self) -> RiskTier:
        return tier_for(self.events)
