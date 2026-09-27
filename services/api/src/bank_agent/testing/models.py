"""Scripted intent router and transaction resolver, for tests and the port contract suites."""

from collections.abc import Mapping, Sequence
from datetime import datetime

from bank_agent.domain.base import UntrustedText
from bank_agent.domain.identifiers import TransactionId
from bank_agent.domain.intelligence import (
    IntentPrediction,
    IntentScore,
    ModelComponent,
    ModelRef,
    RankedCandidate,
    TransactionDescriptor,
    TransactionResolution,
)
from bank_agent.domain.locale import Language
from bank_agent.domain.transaction import Transaction
from bank_agent.domain.workflow import Intent

FAKE_ROUTER = ModelRef(component=ModelComponent.ROUTER, name="fake", version="1")
FAKE_RESOLVER = ModelRef(component=ModelComponent.RESOLVER, name="fake", version="1")


class FakeIntentRouter:
    """Implements the ``IntentRouter`` port: exact-text scripts, otherwise a default intent."""

    def __init__(
        self,
        default: Intent = Intent.GREETING_OR_OTHER,
        *,
        default_confidence: float = 0.5,
        threshold: float = 0.6,
        scripts: Mapping[str, tuple[Intent, float]] | None = None,
    ) -> None:
        self._default = (default, default_confidence)
        self._threshold = threshold
        self._scripts = dict(scripts or {})

    def set(self, text: str, intent: Intent, confidence: float) -> None:
        self._scripts[text] = (intent, confidence)

    def route(self, text: UntrustedText, language: Language) -> IntentPrediction:
        intent, confidence = self._scripts.get(text, self._default)
        return IntentPrediction(
            intent=intent,
            confidence=confidence,
            candidates=(IntentScore(intent=intent, score=confidence),),
            below_threshold=confidence < self._threshold,
            model=FAKE_ROUTER,
        )


class FakeTransactionResolver:
    """Implements the ``TransactionResolver`` port with scripted scores per transaction id.

    Unscripted candidates score 0. Ties are broken by the most recent transaction, then by id. The top
    candidate is a clear winner when its score beats the runner-up by ``margin`` (or it is the only
    candidate with a positive score).
    """

    def __init__(self, scores: Mapping[str, float] | None = None, *, margin: float = 0.2) -> None:
        self._scores = dict(scores or {})
        self._margin = margin

    def rank(
        self, descriptor: TransactionDescriptor, candidates: Sequence[Transaction], *, now: datetime
    ) -> TransactionResolution:
        unique = {candidate.transaction_id: candidate for candidate in candidates}
        ordered = sorted(
            unique.values(),
            key=lambda txn: (
                -self._scores.get(txn.transaction_id, 0.0),
                -txn.occurred_at.timestamp(),
                txn.transaction_id,
            ),
        )
        ranked = tuple(
            RankedCandidate(
                transaction_id=txn.transaction_id, score=self._scores.get(txn.transaction_id, 0.0), rank=rank
            )
            for rank, txn in enumerate(ordered, start=1)
        )
        margin: float | None = None
        winner: TransactionId | None = None
        if ranked:
            runner_up = ranked[1].score if len(ranked) > 1 else 0.0
            margin = ranked[0].score - runner_up
            if ranked[0].score > 0 and margin >= self._margin:
                winner = ranked[0].transaction_id
        return TransactionResolution(ranked=ranked, margin=margin, clear_winner=winner, model=FAKE_RESOLVER)
