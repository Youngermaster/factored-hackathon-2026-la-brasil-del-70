"""Sentence embeddings for dense retrieval: the ``Embedder`` protocol, the sentence-transformers adapter, and a
disk cache keyed by content hash.

sentence-transformers (with torch) is the optional ``ml`` extra of ``bank-agent`` and is never installed in the
API runtime image. It is imported only when a ``SentenceTransformerEmbedder`` is built, so every other module
imports without it. Vectors are L2-normalized, so a dot product is the cosine similarity.
"""

import hashlib
import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal, Protocol

from bank_agent.domain.errors import EmbeddingBackendUnavailableError

DEFAULT_EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
"""MIT licensed, 118M parameters, 384 dimensions, trained for retrieval in about 100 languages (es and pt too)."""
E5_QUERY_PREFIX = "query: "
E5_PASSAGE_PREFIX = "passage: "
Vector = tuple[float, ...]
TextKind = Literal["query", "passage"]


class Embedder(Protocol):
    """Turns texts into unit-length vectors. ``model_id`` names the model and its prefixes for cache keys."""

    @property
    def model_id(self) -> str: ...

    def embed_passages(self, texts: Sequence[str]) -> list[Vector]: ...

    def embed_query(self, text: str) -> Vector: ...


def normalize(vector: Sequence[float]) -> Vector:
    norm = math.sqrt(sum(value * value for value in vector))
    return tuple(value / norm for value in vector) if norm > 0.0 else tuple(0.0 for _ in vector)


def dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def ml_extra_installed() -> bool:
    """True when sentence-transformers can be imported (the optional ``ml`` extra)."""
    import importlib.util

    return importlib.util.find_spec("sentence_transformers") is not None


class SentenceTransformerEmbedder:
    """A sentence-transformers model loaded from (and downloaded into) ``cache_dir``, run on the CPU."""

    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        *,
        cache_dir: Path,
        query_prefix: str = E5_QUERY_PREFIX,
        passage_prefix: str = E5_PASSAGE_PREFIX,
    ) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # optional ml extra, imported on first use
        except ImportError as error:
            raise EmbeddingBackendUnavailableError(
                "dense retrieval needs the optional ml extra: uv sync --all-packages --extra ml"
            ) from error
        self._model: Any = SentenceTransformer(model_name, cache_folder=str(cache_dir), device="cpu")
        self._name = model_name
        self._query_prefix = query_prefix
        self._passage_prefix = passage_prefix

    @property
    def model_id(self) -> str:
        return f"{self._name}|{self._query_prefix}|{self._passage_prefix}"

    def _encode(self, texts: Sequence[str]) -> list[Vector]:
        encoded = self._model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
        return [normalize([float(value) for value in row]) for row in encoded]

    def embed_passages(self, texts: Sequence[str]) -> list[Vector]:
        return self._encode([f"{self._passage_prefix}{text}" for text in texts])

    def embed_query(self, text: str) -> Vector:
        return self._encode([f"{self._query_prefix}{text}"])[0]


class CachingEmbedder:
    """Wraps an ``Embedder`` with a disk cache: one JSON file per text, named by a SHA-256 of model, kind, text."""

    def __init__(self, inner: Embedder, cache_dir: Path) -> None:
        self._inner = inner
        self._dir = cache_dir
        self.hits = 0
        self.misses = 0

    @property
    def model_id(self) -> str:
        return self._inner.model_id

    def _path(self, kind: TextKind, text: str) -> Path:
        key = hashlib.sha256(f"{self.model_id}\n{kind}\n{text}".encode()).hexdigest()
        return self._dir / key[:2] / f"{key}.json"

    def _read(self, path: Path) -> Vector | None:
        if not path.is_file():
            return None
        values = json.loads(path.read_text(encoding="utf-8"))
        return tuple(float(value) for value in values)

    def _write(self, path: Path, vector: Vector) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(list(vector)), encoding="utf-8")

    def _store(self, kind: TextKind, text: str, vector: Vector) -> Vector:
        self._write(self._path(kind, text), vector)
        self.misses += 1
        return vector

    def embed_passages(self, texts: Sequence[str]) -> list[Vector]:
        cached = [self._read(self._path("passage", text)) for text in texts]
        missing = [text for text, vector in zip(texts, cached, strict=True) if vector is None]
        fresh = iter(self._inner.embed_passages(missing) if missing else [])
        result: list[Vector] = []
        for text, stored in zip(texts, cached, strict=True):
            if stored is None:
                result.append(self._store("passage", text, next(fresh)))
            else:
                self.hits += 1
                result.append(stored)
        return result

    def embed_query(self, text: str) -> Vector:
        path = self._path("query", text)
        vector = self._read(path)
        if vector is None:
            return self._store("query", text, self._inner.embed_query(text))
        self.hits += 1
        return vector
