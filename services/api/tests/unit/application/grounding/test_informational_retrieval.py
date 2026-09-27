"""The retrieval policy (threshold abstention, ELG never returned) and the informational-only gate."""

import pytest

from bank_agent.adapters.retrieval.bm25 import BM25_MODEL, Bm25Index, Bm25Retriever
from bank_agent.application.grounding.retrieval import (
    AbstentionReason,
    InformationalRetrieval,
    RetrievalDecision,
    RetrievalPolicy,
)
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.errors import ConfigurationError, RetrievalNotAllowedError
from bank_agent.domain.intelligence import ModelComponent, ModelRef, RetrievalHit, RetrievalResult
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.workflow import Intent
from bank_agent_builders import customer
from bank_agent_retrieval import FIXTURE_DOCUMENTS


def hit(clause_id: str, score: float, rank: int) -> RetrievalHit:
    return RetrievalHit(clause=ClauseRef(clause_id=clause_id, version=1), score=score, rank=rank)


def result(*hits: RetrievalHit) -> RetrievalResult:
    return RetrievalResult(hits=hits, retriever=BM25_MODEL)


POLICY = RetrievalPolicy({"bm25": 2.0})


def test_answers_with_the_hits_at_or_above_the_threshold() -> None:
    outcome = POLICY.apply(result(hit("DSP-MX-1", 5.0, 1), hit("DSP-MX-2", 2.0, 2), hit("CRD-ALL-1", 1.9, 3)))
    assert outcome.decision is RetrievalDecision.ANSWER
    assert [ref.clause_id for ref in outcome.citations] == ["DSP-MX-1", "DSP-MX-2"]
    assert (outcome.top_score, outcome.threshold, outcome.reason) == (5.0, 2.0, None)


def test_abstains_below_the_threshold_and_without_hits() -> None:
    low = POLICY.apply(result(hit("DSP-MX-1", 1.5, 1)))
    assert low.decision is RetrievalDecision.ABSTAIN
    assert low.reason is AbstentionReason.BELOW_THRESHOLD
    assert (low.hits, low.top_score) == ((), 1.5)
    empty = POLICY.apply(result())
    assert (empty.decision, empty.reason, empty.top_score) == (
        RetrievalDecision.ABSTAIN,
        AbstentionReason.NO_HITS,
        None,
    )


def test_eligibility_clauses_are_never_returned_and_ranks_restart_at_one() -> None:
    outcome = POLICY.apply(result(hit("ELG-MX-1.1", 9.0, 1), hit("CRE-ALL-2", 3.0, 2)))
    assert [(h.clause.clause_id, h.rank) for h in outcome.hits] == [("CRE-ALL-2", 1)]
    assert outcome.top_score == 3.0
    only_elg = POLICY.apply(result(hit("ELG-ALL-1", 9.0, 1)))
    assert only_elg.reason is AbstentionReason.NO_HITS


def test_a_retriever_without_a_threshold_is_a_configuration_error() -> None:
    dense = ModelRef(component=ModelComponent.RETRIEVER, name="dense", version="1")
    with pytest.raises(ConfigurationError, match="no relevance threshold for retriever dense"):
        POLICY.apply(RetrievalResult(hits=(), retriever=dense))


def engine(threshold: float = 0.5) -> InformationalRetrieval:
    return InformationalRetrieval(
        Bm25Retriever(Bm25Index.build(FIXTURE_DOCUMENTS)), RetrievalPolicy({"bm25": threshold})
    )


def test_informational_questions_search_in_the_customer_jurisdiction() -> None:
    outcome = engine().search(
        intent=Intent.INFORMATIONAL,
        text=UntrustedText("¿Cuál es el plazo para presentar una reclamación?"),
        customer=customer(country=Country.CO),
        language=Language.ES,
    )
    assert outcome.decision is RetrievalDecision.ANSWER
    assert "DSP-MX-1" not in [ref.clause_id for ref in outcome.citations]
    assert outcome.citations[0].clause_id == "DSP-CO-1"


def test_out_of_scope_text_abstains() -> None:
    outcome = engine().search(
        intent=Intent.INFORMATIONAL,
        text=UntrustedText("¿Va a llover mañana en Bogotá?"),
        customer=customer(country=Country.CO),
        language=Language.ES,
    )
    assert outcome.decision is RetrievalDecision.ABSTAIN


@pytest.mark.parametrize("intent", [i for i in Intent if i is not Intent.INFORMATIONAL])
def test_every_other_intent_is_refused(intent: Intent) -> None:
    with pytest.raises(RetrievalNotAllowedError):
        engine().search(intent=intent, text=UntrustedText("plazo"), customer=customer(), language=Language.ES)


def test_k_is_bounded() -> None:
    with pytest.raises(ValueError, match="between 1 and 20"):
        InformationalRetrieval(Bm25Retriever(Bm25Index.build(FIXTURE_DOCUMENTS)), POLICY, k=0)
