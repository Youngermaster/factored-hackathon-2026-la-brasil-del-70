"""Recorded embeddings: a committed, versioned file of vectors, so evaluations and tests run offline.

The file is JSON Lines. The first line is the header: ``format``, ``model_id`` (with the dimension, for example
``azure/text-embedding-3-small|512``), ``dimension``, ``recorded_at``, and ``source``. Every other line is one
vector: ``kind`` (``passage`` or ``query``), ``key`` (the SHA-256 of the kind and the text), and ``vector`` (base64 of
little-endian float32 values). Keys are hashes, so the file holds no text; lines are sorted by kind and key, so a
regeneration diffs cleanly.

Replay (no inner embedder) never calls a model: a text without a recorded vector raises ``EmbeddingRejectedError``
naming the regeneration command. Record mode embeds only the missing texts with the inner embedder (the hosted
gateway on the evaluation account) and ``save`` rewrites the file. Sits below the redaction decorator, so a query is
recorded under its redacted text, exactly as production embeds it.
"""

import base64
import hashlib
import json
import struct
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Final, Literal

from bank_agent.domain.errors import EmbeddingRejectedError
from bank_agent.domain.vectors import Vector
from bank_agent.ports.embeddings import Embedder

FORMAT: Final = 1
RECORD_COMMAND: Final = "make eval-retrieval-embeddings"
Kind = Literal["passage", "query"]


def record_key(kind: Kind, text: str) -> str:
    return hashlib.sha256(f"{kind}\n{text}".encode()).hexdigest()


def encode_vector(vector: Sequence[float]) -> str:
    return base64.b64encode(struct.pack(f"<{len(vector)}f", *vector)).decode("ascii")


def decode_vector(encoded: str, dimension: int) -> Vector:
    raw = base64.b64decode(encoded.encode("ascii"), validate=True)
    if len(raw) != 4 * dimension:
        raise EmbeddingRejectedError("a recorded vector has another dimension than its file")
    return tuple(float(value) for value in struct.unpack(f"<{dimension}f", raw))


class RecordedEmbedder:
    """``Embedder`` over a recorded file; with ``inner``, records the vectors it is missing."""

    def __init__(self, path: Path, *, model_id: str, inner: Embedder | None = None) -> None:
        if inner is not None and inner.model_id != model_id:
            raise EmbeddingRejectedError("the recording model differs from the embedder that would fill it")
        self.path = path
        self._model_id = model_id
        self._inner = inner
        self._dimension: int | None = None
        self._vectors: dict[str, Vector] = {}
        self.recorded_at: str | None = None
        self.source: str | None = None
        self.hits = 0
        self.misses = 0
        if path.is_file():
            self._load()

    @classmethod
    def replay(cls, path: Path) -> "RecordedEmbedder":
        """Read the model id from the file's header; every text must be recorded."""
        if not path.is_file():
            raise EmbeddingRejectedError(f"no recorded embeddings at {path.name}; run {RECORD_COMMAND}")
        header = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        return cls(path, model_id=str(header["model_id"]))

    def _load(self) -> None:
        lines = self.path.read_text(encoding="utf-8").splitlines()
        header = json.loads(lines[0])
        if header.get("format") != FORMAT or header.get("model_id") != self._model_id:
            raise EmbeddingRejectedError(f"{self.path.name} records another model or format; run {RECORD_COMMAND}")
        self._dimension = int(header["dimension"])
        self.recorded_at = header.get("recorded_at")
        self.source = header.get("source")
        for line in lines[1:]:
            if line.strip():
                item = json.loads(line)
                self._vectors[f"{item['kind']}:{item['key']}"] = decode_vector(item["vector"], self._dimension)

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def dimension(self) -> int | None:
        return self._dimension

    def __len__(self) -> int:
        return len(self._vectors)

    def _embed(self, kind: Kind, texts: Sequence[str]) -> list[Vector]:
        keys = [f"{kind}:{record_key(kind, text)}" for text in texts]
        missing = [text for text, key in zip(texts, keys, strict=True) if key not in self._vectors]
        if missing:
            if self._inner is None:
                raise EmbeddingRejectedError(
                    f"{len(missing)} {kind} text(s) have no recorded embedding in {self.path.name}; "
                    f"run {RECORD_COMMAND}"
                )
            fresh = (
                self._inner.embed_passages(missing)
                if kind == "passage"
                else [self._inner.embed_query(text) for text in missing]
            )
            for text, vector in zip(missing, fresh, strict=True):
                self._dimension = self._dimension or len(vector)
                self._vectors[f"{kind}:{record_key(kind, text)}"] = vector
            self.misses += len(missing)
        self.hits += len(texts) - len(missing)
        return [self._vectors[key] for key in keys]

    def embed_passages(self, texts: Sequence[str]) -> list[Vector]:
        return self._embed("passage", texts)

    def embed_query(self, text: str) -> Vector:
        return self._embed("query", [text])[0]

    def save(self, *, recorded_at: datetime, source: str) -> None:
        """Rewrite the file with every vector, sorted; the header records when and from where."""
        if self._dimension is None:
            raise EmbeddingRejectedError("there is nothing to record")
        stamp = recorded_at.isoformat()
        header = {
            "format": FORMAT,
            "model_id": self._model_id,
            "dimension": self._dimension,
            "recorded_at": stamp,
            "source": source,
        }
        lines = [json.dumps(header, sort_keys=True)]
        for composite in sorted(self._vectors):
            kind, key = composite.split(":", 1)
            item = {"kind": kind, "key": key, "vector": encode_vector(self._vectors[composite])}
            lines.append(json.dumps(item, sort_keys=True))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.recorded_at, self.source = stamp, source
