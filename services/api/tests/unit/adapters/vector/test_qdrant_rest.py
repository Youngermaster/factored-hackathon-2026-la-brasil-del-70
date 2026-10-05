"""The Qdrant REST adapter against an ``httpx.MockTransport`` that replays Qdrant's responses (no container).

The replies follow Qdrant's REST shapes (``{"result": ..., "status": "ok", "time": ...}``); the real-server check is
the shared contract suite under the ``integration`` marker, which CI runs against the pinned image.
"""

import json
import uuid
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from bank_agent.adapters.vector.qdrant import QdrantVectorStore
from bank_agent.domain.errors import VectorCollectionMissingError, VectorStoreError, VectorStoreRejectedError
from bank_agent.domain.vectors import FieldMatch, PayloadFilter, VectorPoint

Handler = Callable[[httpx.Request], httpx.Response]


def ok(result: Any) -> httpx.Response:
    return httpx.Response(200, json={"result": result, "status": "ok", "time": 0.0001})


def store(handler: Handler) -> tuple[QdrantVectorStore, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.Client(base_url="http://qdrant:6333", transport=httpx.MockTransport(record))
    return QdrantVectorStore("http://qdrant:6333", client=client), seen


def collection_body(size: int = 3, points: int = 2, distance: str = "Cosine") -> dict[str, Any]:
    return {
        "status": "green",
        "points_count": points,
        "config": {"params": {"vectors": {"size": size, "distance": distance}}},
    }


def test_search_sends_the_filter_and_maps_the_points() -> None:
    first, second = uuid.UUID(int=1), uuid.UUID(int=2)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/collections/policy-clauses/points/query"
        return ok(
            {
                "points": [
                    {"id": str(second), "version": 1, "score": 0.5, "payload": {"clause_id": "B", "flag": True}},
                    {"id": str(first), "version": 1, "score": 0.9, "payload": {"clause_id": "A", "version": 1}},
                ]
            }
        )

    adapter, seen = store(handler)
    where = PayloadFilter(
        must=(FieldMatch(key="language", any_of=("pt",)), FieldMatch(key="jurisdiction", any_of=("BR", "ALL")))
    )
    matches = adapter.search("policy-clauses", (1.0, 0.0, 0.0), limit=2, where=where)
    body = json.loads(seen[0].content)
    assert body == {
        "query": [1.0, 0.0, 0.0],
        "limit": 2,
        "filter": {
            "must": [
                {"key": "language", "match": {"any": ["pt"]}},
                {"key": "jurisdiction", "match": {"any": ["BR", "ALL"]}},
            ]
        },
        "with_payload": True,
    }
    assert [match.id for match in matches] == [first, second]
    # Booleans and nested values are dropped: the payload holds keyword strings and integers only.
    assert matches[1].payload == {"clause_id": "B"}
    assert matches[0].payload == {"clause_id": "A", "version": 1}


def test_ensure_collection_creates_a_cosine_collection_and_its_keyword_indexes() -> None:
    created: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            if created:
                return ok(collection_body(points=0))
            return httpx.Response(404, json={"status": {"error": "Not found: Collection `c` doesn't exist!"}})
        if request.url.path == "/collections/c":
            created.update(json.loads(request.content))
            return ok(True)
        assert request.url.path == "/collections/c/index"
        assert request.url.params["wait"] == "true"
        return ok({"operation_id": 1, "status": "completed"})

    adapter, seen = store(handler)
    assert adapter.ensure_collection("c", dimension=3, keyword_fields=("language", "workflow")) is True
    assert created == {"vectors": {"size": 3, "distance": "Cosine"}}
    indexes = [json.loads(request.content) for request in seen if request.url.path.endswith("/index")]
    assert indexes == [
        {"field_name": "language", "field_schema": "keyword"},
        {"field_name": "workflow", "field_schema": "keyword"},
    ]
    assert adapter.ensure_collection("c", dimension=3, keyword_fields=()) is False
    with pytest.raises(VectorStoreRejectedError, match="dimension 3"):
        adapter.ensure_collection("c", dimension=4, keyword_fields=())


def test_upsert_waits_and_sends_batches_of_at_most_128_points() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path == "/collections/c/points"
        assert request.url.params["wait"] == "true"
        return ok({"operation_id": 2, "status": "completed"})

    adapter, seen = store(handler)
    points = [VectorPoint(id=uuid.UUID(int=n + 1), vector=(1.0, 0.0), payload={"n": n}) for n in range(130)]
    adapter.upsert("c", points)
    sizes = [len(json.loads(request.content)["points"]) for request in seen]
    assert sizes == [128, 2]
    assert json.loads(seen[1].content)["points"][0] == {
        "id": str(uuid.UUID(int=129)),
        "vector": [1.0, 0.0],
        "payload": {"n": 128},
    }


@pytest.mark.parametrize(
    ("status", "error"),
    [(404, VectorCollectionMissingError), (400, VectorStoreRejectedError), (503, VectorStoreError)],
)
def test_maps_statuses_to_typed_errors_without_the_response_body(status: int, error: type[Exception]) -> None:
    adapter, _ = store(lambda request: httpx.Response(status, json={"status": {"error": "secret query text"}}))
    with pytest.raises(error) as raised:
        adapter.search("c", (1.0,), limit=1, where=PayloadFilter())
    assert "secret" not in str(raised.value)


def test_a_timeout_or_an_unreachable_store_is_a_retryable_store_error() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    for handler in (timeout, refused):
        adapter, _ = store(handler)
        with pytest.raises(VectorStoreError) as raised:
            adapter.search("c", (1.0,), limit=1, where=PayloadFilter())
        assert raised.value.retryable is True


def test_malformed_replies_are_store_errors() -> None:
    bodies: list[dict[str, Any]] = [{"result": {"points": [{"id": "not-a-uuid", "score": 1.0}]}}, {"result": {}}]
    for body in bodies:
        adapter, _ = store(lambda request, body=body: httpx.Response(200, json=body))  # type: ignore[misc]
        with pytest.raises(VectorStoreError, match="malformed"):
            adapter.search("c", (1.0,), limit=1, where=PayloadFilter())
    adapter, _ = store(lambda request: httpx.Response(200, content=b"not json"))
    with pytest.raises(VectorStoreError, match="malformed"):
        adapter.list_collections()


def test_refuses_a_collection_that_does_not_use_cosine_distance() -> None:
    adapter, _ = store(lambda request: ok(collection_body(distance="Dot")))
    with pytest.raises(VectorStoreRejectedError, match="cosine"):
        adapter.collection("c")


def test_lists_collections_sorted_and_deletes_only_an_existing_one() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/collections":
            return ok({"collections": [{"name": "b"}, {"name": "a"}]})
        if request.method == "GET":
            return ok(collection_body()) if request.url.path == "/collections/a" else httpx.Response(404)
        return ok(True)

    adapter, seen = store(handler)
    assert adapter.list_collections() == ("a", "b")
    assert adapter.delete_collection("a") is True
    assert adapter.delete_collection("missing") is False
    assert [request.method for request in seen if request.url.path == "/collections/missing"] == ["GET"]


def test_refuses_an_invalid_collection_name_or_limit_before_any_request() -> None:
    adapter, seen = store(lambda request: ok(None))
    with pytest.raises(VectorStoreRejectedError):
        adapter.search("../admin", (1.0,), limit=1, where=PayloadFilter())
    with pytest.raises(VectorStoreRejectedError):
        adapter.search("c", (1.0,), limit=0, where=PayloadFilter())
    assert seen == []
    with pytest.raises(VectorStoreRejectedError):
        QdrantVectorStore("")
