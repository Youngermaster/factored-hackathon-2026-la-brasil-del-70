"""Okapi BM25: the scoring formula, filtering by language and jurisdiction, and the stored payload."""

import math

import pytest

from bank_agent.adapters.retrieval.bm25 import BM25_MODEL, Bm25Index, Bm25Parameters, Bm25Retriever
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.errors import RetrievalIndexError
from bank_agent.domain.intelligence import RetrievalQuery
from bank_agent.domain.locale import Country, Language
from bank_agent_retrieval import FIXTURE_DOCUMENTS, document

SMALL = (
    document("CRD-ALL-1", "tarjeta bloqueo"),  # fixtur, tarjet, bloque: length 3
    document("ACC-ALL-1", "tarjeta saldo saldo"),  # fixtur, tarjet, saldo, saldo: length 4
    document("DSP-ALL-1", "plazo"),  # fixtur, plazo: length 2
)


def query(text: str, language: Language = Language.ES, country: Country = Country.MX, k: int = 5) -> RetrievalQuery:
    return RetrievalQuery(text=UntrustedText(text), language=language, jurisdiction=country, k=k)


def test_scores_follow_the_okapi_formula() -> None:
    index = Bm25Index.build(SMALL)
    idf = math.log(1 + (3 - 1 + 0.5) / (1 + 0.5))
    expected = idf * 2 * (1.2 + 1) / (2 + 1.2 * (1 - 0.75 + 0.75 * 4 / 3))
    assert index.idf(Language.ES, "saldo") == pytest.approx(idf)
    assert index.score(1, ("saldo",)) == pytest.approx(expected)
    assert index.score(0, ("saldo",)) == 0.0


def test_a_repeated_query_term_counts_once_and_common_terms_weigh_less() -> None:
    index = Bm25Index.build(SMALL)
    assert index.score(1, ("saldo", "saldo")) == pytest.approx(index.score(1, ("saldo",)))
    assert index.idf(Language.ES, "tarjet") < index.idf(Language.ES, "saldo")
    assert index.idf(Language.ES, "absent") > index.idf(Language.ES, "saldo") > 0


def test_parameters_change_the_score() -> None:
    flat = Bm25Index.build(SMALL, Bm25Parameters(k1=1.2, b=0.0))
    assert flat.score(1, ("saldo",)) != pytest.approx(Bm25Index.build(SMALL).score(1, ("saldo",)))


def test_retriever_ranks_best_first_and_drops_zero_scores() -> None:
    result = Bm25Retriever(Bm25Index.build(SMALL)).search(query("¿Cuál es el saldo de mi tarjeta?"))
    assert [hit.clause.clause_id for hit in result.hits] == ["ACC-ALL-1", "CRD-ALL-1"]
    assert [hit.rank for hit in result.hits] == [1, 2]
    assert result.hits[0].score > result.hits[1].score > 0
    assert result.retriever == BM25_MODEL


def test_filters_language_and_jurisdiction_before_scoring() -> None:
    retriever = Bm25Retriever(Bm25Index.build(FIXTURE_DOCUMENTS))
    colombia = retriever.search(query("plazo reclamacion", country=Country.CO))
    assert {hit.clause.clause_id for hit in colombia.hits} == {"DSP-CO-1"}
    portuguese = retriever.search(query("prazo cobranca mexico", language=Language.PT))
    assert [hit.clause.clause_id for hit in portuguese.hits] == ["DSP-MX-1"]
    assert retriever.search(query("prazo cobranca", language=Language.PT, country=Country.AR)).hits == ()


def test_k_limits_the_hits_and_an_empty_query_finds_nothing() -> None:
    retriever = Bm25Retriever(Bm25Index.build(FIXTURE_DOCUMENTS))
    assert len(retriever.search(query("plazo tarjeta saldo fixture", k=1)).hits) == 1
    assert retriever.search(query("¿y?")).hits == ()


def test_the_payload_round_trips_and_refuses_another_corpus() -> None:
    index = Bm25Index.build(SMALL)
    restored = Bm25Index.from_payload(SMALL, index.to_payload())
    assert restored.score(1, ("saldo",)) == pytest.approx(index.score(1, ("saldo",)))
    with pytest.raises(RetrievalIndexError, match="another corpus"):
        Bm25Index.from_payload(SMALL[:2], index.to_payload())
    with pytest.raises(RetrievalIndexError, match="one term count table"):
        Bm25Index(SMALL, [{}])
