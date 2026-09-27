"""The rule resolver: evidence parts, plausibility, the clear-winner margin, and tie breaking."""

from datetime import date, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from bank_agent.adapters.models.rules_resolver import (
    RULES_RESOLVER,
    RuleTransactionResolver,
    amount_score,
    date_score,
    merchant_score,
)
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.intelligence import DateRange, TransactionDescriptor
from bank_agent.domain.transaction import TransactionChannel
from bank_agent_builders import T0, transaction

NOW = T0.astimezone(ZoneInfo("America/Mexico_City"))
RESOLVER = RuleTransactionResolver()


def described(**fields: object) -> TransactionDescriptor:
    return TransactionDescriptor.model_validate(fields)


def test_amount_evidence_is_graded() -> None:
    txn = transaction(amount="1000.00")
    assert amount_score(described(amount=Decimal("1000")), txn) == 0.45
    assert amount_score(described(amount=Decimal("1015")), txn) == 0.35
    assert amount_score(described(amount=Decimal("1040")), txn) == 0.2
    assert amount_score(described(amount=Decimal("1500")), txn) == 0.0
    assert amount_score(described(amount=Decimal("1000"), currency_hint="USD"), txn) == 0.0


def test_merchant_and_date_evidence() -> None:
    txn = transaction(merchant_name="FIXTURE MARKET CENTRO", occurred_at=T0 - timedelta(days=3))
    assert merchant_score(described(merchant_text=UntrustedText("el market")), txn) == 0.3
    local_day = (T0 - timedelta(days=3)).astimezone(NOW.tzinfo).date()
    inside = DateRange(start=local_day, end=local_day)
    near = DateRange(start=local_day + timedelta(days=2), end=local_day + timedelta(days=2))
    far = DateRange(start=date(2026, 1, 1), end=date(2026, 1, 2))
    assert date_score(described(date_interpretations=(inside,)), txn, NOW) == 0.2
    assert date_score(described(date_interpretations=(near,)), txn, NOW) == 0.1
    assert date_score(described(date_interpretations=(far,)), txn, NOW) == 0.0
    ambiguous = described(date_interpretations=(inside, far))
    assert date_score(ambiguous, txn, NOW) == 0.0


def test_a_clear_winner_needs_the_margin() -> None:
    target = transaction("TXN-1", amount="1250.00", merchant_name="CAFE LUNA")
    other = transaction("TXN-2", amount="300.00", merchant_name="OTRA TIENDA")
    resolution = RESOLVER.rank(described(amount=Decimal("1250"), merchant_text="cafe luna"), [target, other], now=NOW)
    assert resolution.clear_winner == "TXN-1"
    assert [candidate.transaction_id for candidate in resolution.ranked] == ["TXN-1"]
    assert resolution.model == RULES_RESOLVER


def test_two_similar_transactions_have_no_winner_and_ties_go_to_the_most_recent() -> None:
    older = transaction("TXN-OLD", amount="499.00", occurred_at=T0 - timedelta(days=5))
    newer = transaction("TXN-NEW", amount="499.00", occurred_at=T0 - timedelta(days=2))
    resolution = RESOLVER.rank(described(amount=Decimal("499")), [older, newer, older], now=NOW)
    assert resolution.clear_winner is None
    assert [candidate.transaction_id for candidate in resolution.ranked] == ["TXN-NEW", "TXN-OLD"]
    assert resolution.margin == 0.0


def test_no_evidence_ranks_nothing() -> None:
    resolution = RESOLVER.rank(described(), [transaction()], now=NOW)
    assert resolution.ranked == ()
    assert resolution.clear_winner is None


def test_channel_adds_a_little() -> None:
    txn = transaction(channel=TransactionChannel.ATM, amount="200.00")
    resolution = RESOLVER.rank(described(amount=Decimal("200"), channel_hint="atm"), [txn], now=NOW)
    assert resolution.ranked[0].score == 0.5
