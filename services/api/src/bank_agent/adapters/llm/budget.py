"""Budget guard: a per-session token cap, a per-conversation cost cap, and a daily cost cap.

Before a call the guard reserves the worst case of the reply (``max_output_tokens`` at the highest effective
output price among the configured models) and raises ``LlmBudgetExceededError`` when the reservation would
cross a cap. After a successful call it replaces the reservation with the actual tokens and cost (the result's
``cost_usd`` when present, otherwise the conservative price-table cost). After ``invalid_output`` or a timeout it
keeps the reservation, because the provider may have billed tokens the error does not report; after any other
error it releases it.

The session cap applies to calls that carry a lineage id, the conversation cap to calls that carry a
conversation id, and the daily cap (a UTC day on the ``Clock``) to every call. The ledger is in memory, per
process; a shared ledger is backlog work for phase 15.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from bank_agent.adapters.llm.prices import PriceTable
from bank_agent.adapters.llm.request import Generation, LlmDecorator, LlmRequest, Proceed
from bank_agent.domain.errors import LlmBudgetExceededError, LlmInvalidOutputError, LlmTimeoutError
from bank_agent.ports.determinism import Clock
from bank_agent.ports.llm import LLMClient


@dataclass(frozen=True, slots=True)
class BudgetLimits:
    session_token_limit: int
    conversation_cost_limit_usd: Decimal
    daily_cost_limit_usd: Decimal

    def __post_init__(self) -> None:
        if self.session_token_limit <= 0 or self.conversation_cost_limit_usd < 0 or self.daily_cost_limit_usd < 0:
            raise ValueError("budget limits must be positive")


@dataclass
class InMemoryBudgetLedger:
    """Spend per session lineage (tokens), per conversation (USD), and per UTC day (USD)."""

    session_tokens: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    conversation_cost: dict[str, Decimal] = field(default_factory=lambda: defaultdict(Decimal))
    daily_cost: dict[date, Decimal] = field(default_factory=lambda: defaultdict(Decimal))

    def add(self, *, session: str | None, conversation: str | None, day: date, tokens: int, cost: Decimal) -> None:
        if session is not None:
            self.session_tokens[session] += tokens
        if conversation is not None:
            self.conversation_cost[conversation] += cost
        self.daily_cost[day] += cost


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
        ledger: InMemoryBudgetLedger | None = None,
    ) -> None:
        super().__init__(inner)
        self.limits = limits
        self.prices = prices
        self.model_ids = model_ids
        self.ledger = ledger if ledger is not None else InMemoryBudgetLedger()
        self._clock = clock

    def _check(self, session: str | None, conversation: str | None, day: date, tokens: int, cost: Decimal) -> None:
        if session is not None and self.ledger.session_tokens[session] + tokens > self.limits.session_token_limit:
            raise LlmBudgetExceededError("the session token cap would be exceeded")
        if (
            conversation is not None
            and self.ledger.conversation_cost[conversation] + cost > self.limits.conversation_cost_limit_usd
        ):
            raise LlmBudgetExceededError("the conversation cost cap would be exceeded")
        if self.ledger.daily_cost[day] + cost > self.limits.daily_cost_limit_usd:
            raise LlmBudgetExceededError("the daily cost cap would be exceeded")

    async def around(self, request: LlmRequest, proceed: Proceed) -> Generation:
        context = request.call_context
        session = context.lineage_id
        conversation = context.conversation_id
        day = self._clock.now().date()
        tokens = request.max_output_tokens
        reserved = self.prices.worst_output_cost(self.model_ids, tokens)
        self._check(session, conversation, day, tokens, reserved)
        self.ledger.add(session=session, conversation=conversation, day=day, tokens=tokens, cost=reserved)
        try:
            result = await proceed(request)
        except (LlmInvalidOutputError, LlmTimeoutError):
            raise
        except BaseException:
            self.ledger.add(session=session, conversation=conversation, day=day, tokens=-tokens, cost=-reserved)
            raise
        cost = result.cost_usd if result.cost_usd is not None else self.prices.cost(result.model_id, result.usage)
        used = result.usage.input_tokens + result.usage.output_tokens
        self.ledger.add(session=session, conversation=conversation, day=day, tokens=used - tokens, cost=cost - reserved)
        return result
