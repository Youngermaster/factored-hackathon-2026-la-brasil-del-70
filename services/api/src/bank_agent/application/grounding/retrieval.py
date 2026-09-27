"""Open retrieval for informational questions, with a relevance threshold and abstention.

Open retrieval is reachable only from the ``informational`` intent, in any of the four workflows; workflow
states get their clauses from the bound lookup instead. The query's jurisdiction comes from the verified customer
record. ``RetrievalPolicy`` keeps hits at or above the retriever's threshold and abstains when none remain. It
also drops any ELG clause, a second guard behind the corpus exclusion: retrieved text never supplies an
eligibility rule, which comes only from the synthetic eligibility service.
"""

from collections.abc import Mapping
from enum import StrEnum

from bank_agent.domain.base import DomainModel, UntrustedText
from bank_agent.domain.customer import Customer
from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.errors import ConfigurationError, RetrievalNotAllowedError
from bank_agent.domain.intelligence import ModelRef, RetrievalHit, RetrievalQuery, RetrievalResult, Score
from bank_agent.domain.locale import Language
from bank_agent.domain.policy import ClauseFamily
from bank_agent.domain.workflow import Intent
from bank_agent.ports.retrieval import Retriever

RETRIEVAL_INTENTS = frozenset({Intent.INFORMATIONAL})
NEVER_RETRIEVED = frozenset({ClauseFamily.ELG})
DEFAULT_ANSWER_K = 3
MAX_K = 20


class RetrievalDecision(StrEnum):
    ANSWER = "answer"
    ABSTAIN = "abstain"


class AbstentionReason(StrEnum):
    NO_HITS = "no_hits"
    BELOW_THRESHOLD = "below_threshold"


class RetrievalOutcome(DomainModel):
    decision: RetrievalDecision
    hits: tuple[RetrievalHit, ...]
    """The hits that cleared the threshold, re-ranked from 1; empty on abstention."""
    top_score: Score | None
    threshold: Score
    retriever: ModelRef
    reason: AbstentionReason | None = None

    @property
    def citations(self) -> tuple[ClauseRef, ...]:
        return tuple(hit.clause for hit in self.hits)


class RetrievalPolicy:
    """A relevance threshold per retriever name (``bm25``, ``dense``, ``hybrid``); scores below it abstain."""

    def __init__(self, thresholds: Mapping[str, float]) -> None:
        self._thresholds = dict(thresholds)

    def threshold(self, retriever: ModelRef) -> float:
        try:
            return self._thresholds[retriever.name]
        except KeyError:
            raise ConfigurationError(f"no relevance threshold for retriever {retriever.name}") from None

    def apply(self, result: RetrievalResult) -> RetrievalOutcome:
        threshold = self.threshold(result.retriever)
        allowed = [hit for hit in result.hits if hit.clause.family not in NEVER_RETRIEVED]
        top = allowed[0].score if allowed else None
        kept = [hit for hit in allowed if hit.score >= threshold]
        if not kept:
            reason = AbstentionReason.NO_HITS if not allowed else AbstentionReason.BELOW_THRESHOLD
            return RetrievalOutcome(
                decision=RetrievalDecision.ABSTAIN,
                hits=(),
                top_score=top,
                threshold=threshold,
                retriever=result.retriever,
                reason=reason,
            )
        hits = tuple(hit.model_copy(update={"rank": rank}) for rank, hit in enumerate(kept, 1))
        return RetrievalOutcome(
            decision=RetrievalDecision.ANSWER, hits=hits, top_score=top, threshold=threshold, retriever=result.retriever
        )


class InformationalRetrieval:
    """The only entry point to open retrieval for the workflows."""

    def __init__(self, retriever: Retriever, policy: RetrievalPolicy, *, k: int = DEFAULT_ANSWER_K) -> None:
        if not 1 <= k <= MAX_K:
            raise ValueError(f"k must be between 1 and {MAX_K}")
        self._retriever = retriever
        self._policy = policy
        self._k = k

    def search(
        self, *, intent: Intent, text: UntrustedText, customer: Customer, language: Language
    ) -> RetrievalOutcome:
        if intent not in RETRIEVAL_INTENTS:
            raise RetrievalNotAllowedError(f"open retrieval is not available for intent {intent}")
        query = RetrievalQuery(text=text, language=language, jurisdiction=customer.country, k=self._k)
        return self._policy.apply(self._retriever.search(query))
