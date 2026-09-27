"""Dense retrieval with the real multilingual embedding model (optional ``ml`` extra; downloads it once).

Every other retrieval test runs on the deterministic fake embedder, so this module only proves the real adapter
works end to end. It is skipped, with the reason shown, only when the extra is not installed.
"""

import pytest

from bank_agent.adapters.policy.filesystem import FilesystemPolicyRepository
from bank_agent.adapters.retrieval.dense import DenseRetriever
from bank_agent.adapters.retrieval.embedding import ml_extra_installed
from bank_agent.adapters.retrieval.index_store import build_index
from bank_agent.bootstrap.retrieval import build_embedder
from bank_agent.bootstrap.settings import DEFAULT_EMBEDDING_CACHE_DIR, DEFAULT_MODEL_CACHE_DIR, DEFAULT_POLICY_DIR
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.intelligence import RetrievalQuery
from bank_agent.domain.locale import Country, Language

pytestmark = pytest.mark.skipif(
    not ml_extra_installed(),
    reason="the optional ml extra (sentence-transformers) is not installed: uv sync --all-packages --extra ml",
)


@pytest.fixture(scope="module")
def retriever() -> DenseRetriever:
    embedder = build_embedder(
        "intfloat/multilingual-e5-small",
        model_cache_dir=DEFAULT_MODEL_CACHE_DIR,
        embedding_cache_dir=DEFAULT_EMBEDDING_CACHE_DIR,
    )
    index = build_index(FilesystemPolicyRepository.from_directory(DEFAULT_POLICY_DIR), embedder=embedder)
    assert index.dense is not None
    return DenseRetriever(index.dense, embedder)


@pytest.mark.parametrize(
    ("text", "language", "country", "expected"),
    [
        ("¿Cuántos días tengo para aclarar un cargo que no reconozco?", Language.ES, Country.MX, "DSP-MX-1"),
        ("Qual é o prazo para contestar uma compra que não reconheço?", Language.PT, Country.AR, "DSP-AR-1"),
        ("Perdí mi tarjeta, ¿la pueden bloquear?", Language.ES, Country.CO, "CRD-ALL-2"),
    ],
)
def test_the_real_model_ranks_the_governing_clause_near_the_top(
    retriever: DenseRetriever, text: str, language: Language, country: Country, expected: str
) -> None:
    query = RetrievalQuery(text=UntrustedText(text), language=language, jurisdiction=country, k=3)
    result = retriever.search(query)
    assert expected in [hit.clause.clause_id for hit in result.hits]
    assert result.retriever.version == "intfloat.multilingual-e5-small"
    assert 0.0 < result.hits[0].score <= 1.0
