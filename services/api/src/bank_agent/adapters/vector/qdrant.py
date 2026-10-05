"""Qdrant behind the ``VectorStore`` port, over its REST API with httpx (ADR 0047).

A small adapter instead of ``qdrant-client``: the port needs six calls, and the official client would bring gRPC and
its generated stubs into the API image. Every call has a bounded timeout and no retry: a failed search makes the
retrieval fallback answer with BM25 at once, which is cheaper for the customer than waiting for a second attempt.

Errors map by status: 404 is ``VectorCollectionMissingError``, any other 4xx ``VectorStoreRejectedError`` (never
retried), and a 5xx, a timeout, or a transport failure ``VectorStoreError``. Messages carry the status only, never
the response body, which may quote the request.
"""

import re
import uuid
from collections.abc import Mapping, Sequence
from typing import Any, Final
from urllib.parse import quote

import httpx

from bank_agent.domain.errors import (
    VectorCollectionMissingError,
    VectorStoreError,
    VectorStoreRejectedError,
)
from bank_agent.domain.vectors import (
    COLLECTION_NAME_PATTERN,
    CollectionInfo,
    PayloadFilter,
    PayloadValue,
    Vector,
    VectorMatch,
    VectorPoint,
)

DISTANCE: Final = "Cosine"
UPSERT_BATCH: Final = 128


def _filter(where: PayloadFilter) -> dict[str, Any]:
    return {"must": [{"key": item.key, "match": {"any": list(item.any_of)}} for item in where.must]}


def _payload(raw: object) -> dict[str, PayloadValue]:
    if not isinstance(raw, Mapping):
        return {}
    return {
        str(key): value for key, value in raw.items() if isinstance(value, str | int) and not isinstance(value, bool)
    }


class QdrantVectorStore:
    """``VectorStore`` over Qdrant's REST API. Thread-safe (httpx clients are), so worker threads can share it."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 2.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not base_url:
            raise VectorStoreRejectedError("no vector store URL is configured")
        timeout = httpx.Timeout(timeout_seconds, connect=min(1.0, timeout_seconds))
        self._client = client or httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _path(name: str, suffix: str = "") -> str:
        if not re.fullmatch(COLLECTION_NAME_PATTERN, name):
            raise VectorStoreRejectedError("the collection name is not valid")
        return f"/collections/{quote(name, safe='')}{suffix}"

    def _request(
        self, method: str, path: str, *, json: Mapping[str, Any] | None = None, missing_ok: bool = False
    ) -> Any:
        try:
            response = self._client.request(method, path, json=json)
        except httpx.TimeoutException:
            raise VectorStoreError("the vector store timed out") from None
        except httpx.HTTPError as error:
            raise VectorStoreError(f"the vector store is unreachable ({type(error).__name__})") from None
        status = response.status_code
        if status == 404:
            if missing_ok:
                return None
            raise VectorCollectionMissingError("the collection does not exist")
        if 400 <= status < 500:
            raise VectorStoreRejectedError(f"the vector store refused the request (status {status})")
        if status >= 500:
            raise VectorStoreError(f"the vector store failed (status {status})")
        try:
            body = response.json()
        except ValueError:
            raise VectorStoreError("the vector store returned a malformed response") from None
        return body.get("result") if isinstance(body, Mapping) else None

    def collection(self, name: str) -> CollectionInfo | None:
        result = self._request("GET", self._path(name), missing_ok=True)
        if result is None:
            return None
        try:
            vectors = result["config"]["params"]["vectors"]
            dimension = int(vectors["size"])
            points = int(result.get("points_count") or 0)
        except (KeyError, TypeError, ValueError):
            raise VectorStoreError("the vector store returned a malformed collection description") from None
        if vectors.get("distance") != DISTANCE:
            raise VectorStoreRejectedError(f"collection {name} does not use cosine distance")
        return CollectionInfo(name=name, dimension=dimension, points=points)

    def ensure_collection(self, name: str, *, dimension: int, keyword_fields: Sequence[str]) -> bool:
        if dimension < 1:
            raise VectorStoreRejectedError("a collection needs a positive dimension")
        existing = self.collection(name)
        created = False
        if existing is None:
            self._request("PUT", self._path(name), json={"vectors": {"size": dimension, "distance": DISTANCE}})
            created = True
        elif existing.dimension != dimension:
            raise VectorStoreRejectedError(f"collection {name} has dimension {existing.dimension}, not {dimension}")
        for field_name in keyword_fields:
            # Idempotent: Qdrant keeps an existing index with the same schema.
            self._request(
                "PUT",
                self._path(name, "/index?wait=true"),
                json={"field_name": field_name, "field_schema": "keyword"},
            )
        return created

    def list_collections(self) -> tuple[str, ...]:
        result = self._request("GET", "/collections")
        try:
            return tuple(sorted(str(item["name"]) for item in result["collections"]))
        except (KeyError, TypeError):
            raise VectorStoreError("the vector store returned a malformed collection list") from None

    def upsert(self, name: str, points: Sequence[VectorPoint]) -> None:
        path = self._path(name, "/points?wait=true")
        for start in range(0, len(points), UPSERT_BATCH):
            batch = points[start : start + UPSERT_BATCH]
            body = {
                "points": [
                    {"id": str(point.id), "vector": list(point.vector), "payload": dict(point.payload)}
                    for point in batch
                ]
            }
            self._request("PUT", path, json=body)

    def search(self, name: str, vector: Vector, *, limit: int, where: PayloadFilter) -> tuple[VectorMatch, ...]:
        if limit < 1:
            raise VectorStoreRejectedError("the search limit must be positive")
        body = {"query": list(vector), "limit": limit, "filter": _filter(where), "with_payload": True}
        result = self._request("POST", self._path(name, "/points/query"), json=body)
        try:
            raw_points = result["points"]
            matches = [
                VectorMatch(
                    id=uuid.UUID(str(item["id"])), score=float(item["score"]), payload=_payload(item.get("payload"))
                )
                for item in raw_points
            ]
        except (KeyError, TypeError, ValueError):
            raise VectorStoreError("the vector store returned a malformed search result") from None
        matches.sort(key=lambda match: (-match.score, str(match.id)))
        return tuple(matches[:limit])

    def delete_collection(self, name: str) -> bool:
        if self.collection(name) is None:
            return False
        result = self._request("DELETE", self._path(name), missing_ok=True)
        return bool(result)
