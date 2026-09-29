"""Budget guard: a per-session token cap, a per-conversation cost cap, and a daily cost cap.

Before a call the guard reserves the worst case of the reply (``max_output_tokens`` at the highest effective
output price among the configured models) and raises ``LlmBudgetExceededError`` when the reservation would
cross a cap. After a successful call it replaces the reservation with the actual tokens and cost (the result's
``cost_usd`` when present, otherwise the conservative price-table cost). After ``invalid_output`` or a timeout it
keeps the reservation, because the provider may have billed tokens the error does not report; after any other
error it releases it.

The session cap applies to calls that carry a lineage id, the conversation cap to calls that carry a
conversation id, and the daily cap (a UTC day on the ``Clock``) to every call. The counters live in a
``BudgetLedger``: in memory for one process (tests, the evaluation harness, a single worker), or in PostgreSQL
(``PostgresBudgetLedger``) so every API worker enforces the same caps. The guard remembers the day's spend it last
saw, so the degradation monitor can read the ratio without I/O: at 80 percent it logs ``llm_budget_alert`` once a
day (Prometheus alerts on the gauge), and at 100 percent the ladder switches to template-only mode (L2).
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Final

import structlog

from bank_agent.adapters.llm.prices import PriceTable
from bank_agent.adapters.llm.request import Generation, LlmDecorator, LlmRequest, Proceed
from bank_agent.domain.errors import LlmBudgetExceededError, LlmInvalidOutputError, LlmTimeoutError
from bank_agent.ports.budget import BudgetCap, BudgetLedger, BudgetLimits, BudgetScope, Reservation
from bank_agent.ports.determinism import Clock
from bank_agent.ports.llm import LLMClient
from bank_agent.ports.telemetry import Telemetry

__all__ = ["BudgetGuardDecorator", "BudgetLimits", "InMemoryBudgetLedger"]
_log = structlog.get_logger(__name__)
ALERT_RATIO: Final = 0.8
REFUSALS: Final[dict[BudgetCap, str]] = {
    BudgetCap.SESSION_TOKENS: "the session token cap would be exceeded",
    BudgetCap.CONVERSATION_COST: "the conversation cost cap would be exceeded",
    BudgetCap.DAILY_COST: "the daily cost cap would be exceeded",
}


def first_refusal(
    limits: BudgetLimits, *, session_tokens: int, conversation_cost: Decimal, daily_cost: Decimal, scope: BudgetScope
) -> BudgetCap | None:
    """The first cap that the counters (after adding the reservation) cross, in the order the guard reports them."""
    if scope.session is not None and session_tokens > limits.session_token_limit:
        return BudgetCap.SESSION_TOKENS
    if scope.conversation is not None and conversation_cost > limits.conversation_cost_limit_usd:
        return BudgetCap.CONVERSATION_COST
    if daily_cost > limits.daily_cost_limit_usd:
        return BudgetCap.DAILY_COST
    return None


@dataclass
class InMemoryBudgetLedger:
    """Implements ``BudgetLedger`` for one process: spend per session lineage (tokens), conversation, and day (USD)."""

    session_tokens: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    conversation_cost: dict[str, Decimal] = field(default_factory=lambda: defaultdict(Decimal))
    daily_cost: dict[date, Decimal] = field(default_factory=lambda: defaultdict(Decimal))

    def add(self, *, session: str | None, conversation: str | None, day: date, tokens: int, cost: Decimal) -> None:
        if session is not None:
            self.session_tokens[session] = max(0, self.session_tokens[session] + tokens)
        if conversation is not None:
            self.conversation_cost[conversation] = max(Decimal(0), self.conversation_cost[conversation] + cost)
        self.daily_cost[day] = max(Decimal(0), self.daily_cost[day] + cost)

    async def reserve(self, scope: BudgetScope, *, tokens: int, cost: Decimal, limits: BudgetLimits) -> Reservation:
        refused = first_refusal(
            limits,
            session_tokens=self.session_tokens[scope.session] + tokens if scope.session is not None else 0,
            conversation_cost=(
                self.conversation_cost[scope.conversation] + cost if scope.conversation is not None else Decimal(0)
            ),
            daily_cost=self.daily_cost[scope.day] + cost,
            scope=scope,
        )
        if refused is None:
            self.add(session=scope.session, conversation=scope.conversation, day=scope.day, tokens=tokens, cost=cost)
        return Reservation(refused_by=refused, daily_spent_usd=self.daily_cost[scope.day])

    async def settle(self, scope: BudgetScope, *, tokens: int, cost: Decimal) -> Decimal:
        self.add(session=scope.session, conversation=scope.conversation, day=scope.day, tokens=tokens, cost=cost)
        return self.daily_cost[scope.day]


class BudgetGuardDecorator(LlmDecorator):
    """Refuses calls that would exceed a budget cap and records what each call spent."""

    def __init__(
        self,
        inner: LLMClient,
        *,
        limits: BudgetLimits,
        prices: PriceTable,
        model_ids: tuple[str, ...],
        clock: Clock,
        ledger: BudgetLedger | None = None,
        telemetry: Telemetry | None = None,
    ) -> None:
        super().__init__(inner)
        self.limits = limits
        self.prices = prices
        self.model_ids = model_ids
        self.ledger: BudgetLedger = ledger if ledger is not None else InMemoryBudgetLedger()
        self._clock = clock
        self._refusals = telemetry.counter("bank.llm.budget.refusals") if telemetry is not None else None
        self._seen: tuple[date, Decimal] | None = None
        self._exhausted_on: date | None = None
        self._alerted_on: date | None = None

    def daily_used_ratio(self, day: date) -> float:
        """The share of the daily cap spent, as of the last call this process made on ``day`` (0 before any)."""
        if self._seen is None or self._seen[0] != day:
            return 0.0
        limit = self.limits.daily_cost_limit_usd
        return 1.0 if limit <= 0 else float(self._seen[1] / limit)

    def daily_exhausted(self, day: date) -> bool:
        """True once the daily cap refused a call on ``day``, or the spend reached the cap."""
        return self._exhausted_on == day or self.daily_used_ratio(day) >= 1.0

    def _saw(self, day: date, spent: Decimal) -> None:
        self._seen = (day, spent)
        if self._alerted_on != day and self.daily_used_ratio(day) >= ALERT_RATIO:
            self._alerted_on = day
            _log.warning("llm_budget_alert", daily_used_ratio=round(self.daily_used_ratio(day), 4))

    async def around(self, request: LlmRequest, proceed: Proceed) -> Generation:
        context = request.call_context
        scope = BudgetScope(
            session=context.lineage_id, conversation=context.conversation_id, day=self._clock.now().date()
        )
        tokens = request.max_output_tokens
        reserved = self.prices.worst_output_cost(self.model_ids, tokens)
        reservation = await self.ledger.reserve(scope, tokens=tokens, cost=reserved, limits=self.limits)
        self._saw(scope.day, reservation.daily_spent_usd)
        if reservation.refused_by is not None:
            if reservation.refused_by is BudgetCap.DAILY_COST:
                self._exhausted_on = scope.day
            if self._refusals is not None:
                self._refusals.add(1, {"bank.llm.budget.cap": reservation.refused_by.value})
            raise LlmBudgetExceededError(REFUSALS[reservation.refused_by])
        try:
            result = await proceed(request)
        except (LlmInvalidOutputError, LlmTimeoutError):
            raise
        except BaseException:
            self._saw(scope.day, await self.ledger.settle(scope, tokens=-tokens, cost=-reserved))
            raise
        cost = result.cost_usd if result.cost_usd is not None else self.prices.cost(result.model_id, result.usage)
        used = result.usage.input_tokens + result.usage.output_tokens
        self._saw(scope.day, await self.ledger.settle(scope, tokens=used - tokens, cost=cost - reserved))
        return result
