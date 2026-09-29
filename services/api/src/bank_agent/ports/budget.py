"""Budget ledger port: model spend per session lineage, per conversation, and per UTC day, shared by processes."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Protocol


class BudgetCap(StrEnum):
    SESSION_TOKENS = "session_tokens"
    CONVERSATION_COST = "conversation_cost"
    DAILY_COST = "daily_cost"


@dataclass(frozen=True, slots=True)
class BudgetLimits:
    session_token_limit: int
    conversation_cost_limit_usd: Decimal
    daily_cost_limit_usd: Decimal

    def __post_init__(self) -> None:
        if self.session_token_limit <= 0 or self.conversation_cost_limit_usd < 0 or self.daily_cost_limit_usd < 0:
            raise ValueError("budget limits must be positive")


@dataclass(frozen=True, slots=True)
class BudgetScope:
    """Which counters a call charges: the lineage and the conversation when the call carries them, always the day."""

    session: str | None
    conversation: str | None
    day: date


@dataclass(frozen=True, slots=True)
class Reservation:
    refused_by: BudgetCap | None
    """The first cap the reservation would cross (nothing was added), or ``None`` when it was added."""
    daily_spent_usd: Decimal
    """The day's total after the operation, as the ledger saw it."""


class BudgetLedger(Protocol):
    """Spend counters the budget guard checks and charges.

    Preconditions: amounts are tokens and USD; a negative ``settle`` releases part of an earlier reservation.
    Postconditions: ``reserve`` is atomic across the three counters and across processes sharing the ledger: either
    every counter of the scope grows by the amounts, or none does and the refusing cap is named. Counters never go
    below zero.
    Errors: a storage failure propagates as the adapter's error; the guard then refuses the call (fail closed).
    Isolation: keys are opaque lineage and conversation ids; no customer data, prompt, or reply is stored.
    """

    async def reserve(self, scope: BudgetScope, *, tokens: int, cost: Decimal, limits: BudgetLimits) -> Reservation:
        """Add the reservation to every counter of ``scope`` when no cap would be crossed."""
        ...

    async def settle(self, scope: BudgetScope, *, tokens: int, cost: Decimal) -> Decimal:
        """Adjust every counter of ``scope`` by the amounts (which may be negative); return the day's total."""
        ...
