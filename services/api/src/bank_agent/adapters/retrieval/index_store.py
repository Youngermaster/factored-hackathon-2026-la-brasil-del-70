"""Build, store, and load retrieval indexes keyed by the policy pack version.

An index lives in ``<root>/<pack version>/``: ``manifest.json`` (pack version, corpus digest, tokenizer version,
document count, embedding model), ``bm25.json`` (term counts per document), and, when built with an embedder,
``dense.json`` (one unit vector per document). Loading recomputes the corpus from the loaded pack and refuses an
index whose pack version, corpus digest, tokenizer, or embedding model differs, so the API never answers from
an index built for other policy text.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import NonNegativeInt, StringConstraints, ValidationError

from bank_agent.adapters.retrieval.bm25 import Bm25Index, Bm25Parameters
from bank_agent.adapters.retrieval.corpus import ClauseDocument, build_corpus, corpus_digest
from bank_agent.adapters.retrieval.dense import DenseIndex
from bank_agent.adapters.retrieval.embedding import Embedder
from bank_agent.adapters.retrieval.text import TOKENIZER_VERSION
from bank_agent.domain.base import DomainModel
from bank_agent.domain.errors import RetrievalIndexError
from bank_agent.ports.policy import PolicyRepository

MANIFEST = "manifest.json"
BM25_FILE = "bm25.json"
DENSE_FILE = "dense.json"


class IndexManifest(DomainModel):
    format: Literal[1] = 1
    pack_version: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    corpus_digest: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    tokenizer: str
    document_count: NonNegativeInt
    embedding_model: str | None = None


@dataclass(frozen=True)
class RetrievalIndex:
    manifest: IndexManifest
    documents: tuple[ClauseDocument, ...]
    bm25: Bm25Index
    dense: DenseIndex | None = None


def build_index(
    repository: PolicyRepository,
    *,
    embedder: Embedder | None = None,
    parameters: Bm25Parameters = Bm25Parameters(),  # noqa: B008 - frozen dataclass, safe as a default
) -> RetrievalIndex:
    """Build the BM25 index (and the dense index when an embedder is given) from the pack's current clauses."""
    documents = build_corpus(repository)
    manifest = IndexManifest(
        pack_version=repository.pack_version(),
        corpus_digest=corpus_digest(documents),
        tokenizer=TOKENIZER_VERSION,
        document_count=len(documents),
        embedding_model=embedder.model_id if embedder is not None else None,
    )
    dense = DenseIndex.build(documents, embedder) if embedder is not None else None
    return RetrievalIndex(manifest, documents, Bm25Index.build(documents, parameters), dense)


def write_index(index: RetrievalIndex, root: Path) -> Path:
    """Write the index under ``root/<pack version>/`` and return that directory."""
    directory = root / index.manifest.pack_version
    directory.mkdir(parents=True, exist_ok=True)
    (directory / MANIFEST).write_text(index.manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    (directory / BM25_FILE).write_text(json.dumps(index.bm25.to_payload(), sort_keys=True), encoding="utf-8")
    dense_path = directory / DENSE_FILE
    if index.dense is not None:
        payload = {
            "model_id": index.dense.model_id,
            "documents": [document.key for document in index.dense.documents],
            "vectors": [list(vector) for vector in index.dense.vectors],
        }
        dense_path.write_text(json.dumps(payload), encoding="utf-8")
    elif dense_path.exists():
        dense_path.unlink()
    return directory


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RetrievalIndexError(f"cannot read {path.name} of the retrieval index") from error


def load_index(root: Path, repository: PolicyRepository, *, embedding_model: str | None = None) -> RetrievalIndex:
    """Load the index for the pack's current version; refuse anything built for other text or another model."""
    pack_version = repository.pack_version()
    directory = root / pack_version
    if not (directory / MANIFEST).is_file():
        found = sorted(p.name for p in root.iterdir() if (p / MANIFEST).is_file()) if root.is_dir() else []
        raise RetrievalIndexError(
            f"no retrieval index for pack version {pack_version} (found: {', '.join(found) or 'none'}); "
            "run `bank-agent index build`"
        )
    try:
        manifest = IndexManifest.model_validate(_read_json(directory / MANIFEST))
    except ValidationError as error:
        raise RetrievalIndexError("the retrieval index manifest is malformed") from error
    documents = build_corpus(repository)
    if manifest.pack_version != pack_version:
        raise RetrievalIndexError(f"the index was built for pack version {manifest.pack_version}, not {pack_version}")
    if manifest.tokenizer != TOKENIZER_VERSION:
        raise RetrievalIndexError(f"the index uses tokenizer {manifest.tokenizer}, not {TOKENIZER_VERSION}")
    if manifest.corpus_digest != corpus_digest(documents) or manifest.document_count != len(documents):
        raise RetrievalIndexError("the index was built from another corpus; rebuild it")
    bm25 = Bm25Index.from_payload(documents, _read_json(directory / BM25_FILE))
    dense = None
    if embedding_model is not None:
        if manifest.embedding_model != embedding_model or not (directory / DENSE_FILE).is_file():
            raise RetrievalIndexError(f"the index has no dense vectors for {embedding_model}; rebuild it")
        payload = _read_json(directory / DENSE_FILE)
        if payload.get("documents") != [document.key for document in documents]:
            raise RetrievalIndexError("the stored dense index was built for another corpus")
        vectors = [tuple(float(value) for value in vector) for vector in payload["vectors"]]
        dense = DenseIndex(documents, vectors, payload["model_id"])
    return RetrievalIndex(manifest, documents, bm25, dense)
