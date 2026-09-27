"""``resolver:rules@1``: a transparent rule baseline for the ``TransactionResolver`` port.

Each candidate scores the sum of four evidence parts: amount (exact 0.45, within 2% 0.35, within 5% 0.2),
merchant words (up to 0.3, the share of the customer's merchant words found in the merchant name), date (0.2 inside
a resolved range, 0.1 within two days of it), and channel (0.05). Dates compare in the time zone of ``now``, which
the engine passes in the customer's zone. A candidate needs ``MIN_SCORE`` to rank as plausible; the top candidate
is a clear winner at ``WINNER_SCORE`` or more with a lead of ``MARGIN`` over the runner-up. Ties go to the most
recent transaction, then the id. The resolver never fetches data: it ranks only what it is given.
"""

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal

from bank_agent.application.understanding.text import words
from bank_agent.domain.identifiers import TransactionId
from bank_agent.domain.intelligence import (
    DateRange,
    ModelComponent,
    ModelRef,
    RankedCandidate,
    TransactionDescriptor,
    TransactionResolution,
)
from bank_agent.domain.transaction import Transaction

RULES_RESOLVER = ModelRef(component=ModelComponent.RESOLVER, name="rules", version="1")
MIN_SCORE = 0.2
WINNER_SCORE = 0.35
MARGIN = 0.15
_NEAR_DAYS = 2


def amount_score(descriptor: TransactionDescriptor, txn: Transaction) -> float:
    if descriptor.amount is None:
        return 0.0
    if descriptor.currency_hint is not None and descriptor.currency_hint is not txn.amount.currency:
        return 0.0
    wanted = descriptor.amount
    difference = abs(txn.amount.amount - wanted) / max(wanted, Decimal(1))
    if difference < Decimal("0.005"):
        return 0.45
    if difference <= Decimal("0.02"):
        return 0.35
    if difference <= Decimal("0.05"):
        return 0.2
    return 0.0


def merchant_score(descriptor: TransactionDescriptor, txn: Transaction) -> float:
    if not descriptor.merchant_text or not txn.merchant_name:
        return 0.0
    wanted = {word for word in words(descriptor.merchant_text) if len(word) >= 3}
    found = set(words(txn.merchant_name))
    if not wanted:
        return 0.0
    return round(0.3 * len(wanted & found) / len(wanted), 4)


def _distance(day: date, window: DateRange) -> int:
    if window.start <= day <= window.end:
        return 0
    return (window.start - day).days if day < window.start else (day - window.end).days


def date_score(descriptor: TransactionDescriptor, txn: Transaction, now: datetime) -> float:
    window = descriptor.resolved_date_range
    if window is None:
        return 0.0
    local = txn.occurred_at.astimezone(now.tzinfo).date()
    distance = _distance(local, window)
    if distance == 0:
        return 0.2
    return 0.1 if distance <= _NEAR_DAYS else 0.0


def channel_score(descriptor: TransactionDescriptor, txn: Transaction) -> float:
    return 0.05 if descriptor.channel_hint is not None and descriptor.channel_hint is txn.channel else 0.0


def total_score(descriptor: TransactionDescriptor, txn: Transaction, now: datetime) -> float:
    parts = (
        amount_score(descriptor, txn),
        merchant_score(descriptor, txn),
        date_score(descriptor, txn, now),
        channel_score(descriptor, txn),
    )
    return round(sum(parts), 4)


class RuleTransactionResolver:
    """Implements ``TransactionResolver``."""

    model = RULES_RESOLVER

    def rank(
        self, descriptor: TransactionDescriptor, candidates: Sequence[Transaction], *, now: datetime
    ) -> TransactionResolution:
        unique = {txn.transaction_id: txn for txn in candidates}
        scored = [(total_score(descriptor, txn, now), txn) for txn in unique.values()]
        plausible = [(value, txn) for value, txn in scored if value >= MIN_SCORE]
        plausible.sort(key=lambda item: (-item[0], -item[1].occurred_at.timestamp(), item[1].transaction_id))
        ranked = tuple(
            RankedCandidate(transaction_id=txn.transaction_id, score=value, rank=rank)
            for rank, (value, txn) in enumerate(plausible, start=1)
        )
        margin: float | None = None
        winner: TransactionId | None = None
        if ranked:
            runner_up = ranked[1].score if len(ranked) > 1 else 0.0
            margin = round(ranked[0].score - runner_up, 4)
            if ranked[0].score >= WINNER_SCORE and margin >= MARGIN:
                winner = ranked[0].transaction_id
        return TransactionResolution(ranked=ranked, margin=margin, clear_winner=winner, model=RULES_RESOLVER)
