"""The ``VectorStore`` contract, run against the in-memory store (unit) and a real Qdrant container (integration)."""

import uuid
from collections.abc import Callable, Iterator

import pytest

from bank_agent.adapters.vector.memory import InMemoryVectorStore
from bank_agent.adapters.vector.qdrant import QdrantVectorStore
from bank_agent.domain.errors import VectorCollectionMissingError, VectorStoreRejectedError
from bank_agent.domain.vectors import FieldMatch, PayloadFilter, VectorPoint
from bank_agent.ports.vector_store import VectorStore
from bank_agent_qdrant import qdrant_url  # noqa: F401  (session fixture, started only by the qdrant parameter)

KEYWORDS = ("language", "workflow")


def _memory(request: pytest.FixtureRequest) -> VectorStore:
    return InMemoryVectorStore()


def _qdrant(request: pytest.FixtureRequest) -> VectorStore:
    return QdrantVectorStore(request.getfixturevalue("qdrant_url"), timeout_seconds=10.0)


STORES = [
    pytest.param(_memory, marks=pytest.mark.unit, id="memory"),
    pytest.param(_qdrant, marks=pytest.mark.integration, id="qdrant"),
]


@pytest.fixture(params=STORES)
def store(request: pytest.FixtureRequest) -> Iterator[VectorStore]:
    factory: Callable[[pytest.FixtureRequest], VectorStore] = request.param
    built = factory(request)
    before = set(built.list_collections())
    yield built
    for name in set(built.list_collections()) - before:
        built.delete_collection(name)


@pytest.fixture
def name() -> str:
    return f"contract-{uuid.uuid4().hex[:12]}"


def _point(key: int, vector: tuple[float, ...], **payload: str | int) -> VectorPoint:
    return VectorPoint(id=uuid.UUID(int=key), vector=vector, payload=payload)


POINTS = (
    _point(1, (1.0, 0.0, 0.0), language="es", workflow="dispute", version=1),
    _point(2, (0.8, 0.6, 0.0), language="es", workflow="credit", version=1),
    _point(3, (0.0, 1.0, 0.0), language="pt", workflow="dispute", version=2),
    _point(4, (0.0, 0.0, 1.0), language="pt", workflow="credit", version=1),
)


class TestVectorStoreContract:
    def test_creates_a_collection_once_and_reports_its_dimension(self, store: VectorStore, name: str) -> None:
        assert store.collection(name) is None
        assert store.ensure_collection(name, dimension=3, keyword_fields=KEYWORDS) is True
        assert store.ensure_collection(name, dimension=3, keyword_fields=KEYWORDS) is False
        info = store.collection(name)
        assert info is not None
        assert (info.name, info.dimension, info.points) == (name, 3, 0)
        assert name in store.list_collections()

    def test_refuses_an_existing_collection_with_another_dimension(self, store: VectorStore, name: str) -> None:
        store.ensure_collection(name, dimension=3, keyword_fields=KEYWORDS)
        with pytest.raises(VectorStoreRejectedError):
            store.ensure_collection(name, dimension=4, keyword_fields=KEYWORDS)

    def test_upsert_is_idempotent_by_point_id(self, store: VectorStore, name: str) -> None:
        store.ensure_collection(name, dimension=3, keyword_fields=KEYWORDS)
        store.upsert(name, POINTS)
        store.upsert(name, POINTS)
        replaced = _point(1, (1.0, 0.0, 0.0), language="es", workflow="card_support", version=2)
        store.upsert(name, [replaced])
        info = store.collection(name)
        assert info is not None
        assert info.points == len(POINTS)
        best = store.search(name, (1.0, 0.0, 0.0), limit=1, where=PayloadFilter())
        assert best[0].payload == {"language": "es", "workflow": "card_support", "version": 2}

    def test_ranks_by_cosine_similarity_whatever_the_query_norm(self, store: VectorStore, name: str) -> None:
        store.ensure_collection(name, dimension=3, keyword_fields=KEYWORDS)
        store.upsert(name, POINTS)
        matches = store.search(name, (10.0, 1.0, 0.0), limit=4, where=PayloadFilter())
        assert [match.id.int for match in matches] == [1, 2, 3, 4]
        assert matches[0].score == pytest.approx(10.0 / (101.0**0.5), abs=1e-5)
        assert matches[-1].score == pytest.approx(0.0, abs=1e-5)
        assert [m.score for m in matches] == sorted((m.score for m in matches), reverse=True)

    def test_applies_the_filter_before_ranking(self, store: VectorStore, name: str) -> None:
        store.ensure_collection(name, dimension=3, keyword_fields=KEYWORDS)
        store.upsert(name, POINTS)
        portuguese = PayloadFilter(must=(FieldMatch(key="language", any_of=("pt",)),))
        matches = store.search(name, (1.0, 0.0, 0.0), limit=2, where=portuguese)
        assert {match.id.int for match in matches} == {3, 4}
        assert all(match.payload["language"] == "pt" for match in matches)

    def test_combines_conditions_and_accepts_any_of_several_values(self, store: VectorStore, name: str) -> None:
        store.ensure_collection(name, dimension=3, keyword_fields=KEYWORDS)
        store.upsert(name, POINTS)
        where = PayloadFilter(
            must=(
                FieldMatch(key="workflow", any_of=("dispute", "card_support")),
                FieldMatch(key="language", any_of=("es", "pt")),
                FieldMatch(key="version", any_of=(2,)),
            )
        )
        matches = store.search(name, (1.0, 0.0, 0.0), limit=4, where=where)
        assert [match.id.int for match in matches] == [3]

    def test_returns_at_most_the_limit(self, store: VectorStore, name: str) -> None:
        store.ensure_collection(name, dimension=3, keyword_fields=KEYWORDS)
        store.upsert(name, POINTS)
        assert len(store.search(name, (0.5, 0.5, 0.5), limit=2, where=PayloadFilter())) == 2

    def test_a_missing_collection_is_a_typed_error(self, store: VectorStore, name: str) -> None:
        with pytest.raises(VectorCollectionMissingError):
            store.search(name, (1.0, 0.0, 0.0), limit=1, where=PayloadFilter())
        with pytest.raises(VectorCollectionMissingError):
            store.upsert(name, POINTS[:1])

    def test_refuses_a_point_of_another_dimension(self, store: VectorStore, name: str) -> None:
        store.ensure_collection(name, dimension=3, keyword_fields=KEYWORDS)
        with pytest.raises(VectorStoreRejectedError):
            store.upsert(name, [_point(9, (1.0, 0.0), language="es")])

    def test_deletes_a_collection(self, store: VectorStore, name: str) -> None:
        store.ensure_collection(name, dimension=3, keyword_fields=KEYWORDS)
        assert store.delete_collection(name) is True
        assert store.delete_collection(name) is False
        assert store.collection(name) is None
