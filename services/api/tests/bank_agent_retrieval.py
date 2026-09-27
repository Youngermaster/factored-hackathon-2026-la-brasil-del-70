"""Test support for retrieval: a deterministic fake embedder and small synthetic clause documents.

Every value is synthetic and labeled as a fixture. ``HashingEmbedder`` hashes the tokenizer's tokens into a
fixed number of dimensions, so texts that share words are close, with no model download and no randomness.
"""

import hashlib
from collections.abc import Sequence

from bank_agent.adapters.retrieval.corpus import ClauseDocument
from bank_agent.adapters.retrieval.embedding import Vector, normalize
from bank_agent.adapters.retrieval.text import tokenize
from bank_agent.domain.locale import Language
from bank_agent.domain.policy import ClauseFamily, Jurisdiction

DIMENSIONS = 64


class HashingEmbedder:
    """A deterministic stand-in for a sentence embedding model (fixture). Counts its calls."""

    def __init__(self, language: Language = Language.ES, name: str = "fixture/hashing") -> None:
        self._language = language
        self._name = name
        self.passage_calls = 0
        self.query_calls = 0

    @property
    def model_id(self) -> str:
        return f"{self._name}|q|p"

    def _vector(self, text: str) -> Vector:
        values = [0.0] * DIMENSIONS
        for token in tokenize(text, self._language):
            values[int(hashlib.sha256(token.encode()).hexdigest(), 16) % DIMENSIONS] += 1.0
        return normalize(values)

    def embed_passages(self, texts: Sequence[str]) -> list[Vector]:
        self.passage_calls += 1
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> Vector:
        self.query_calls += 1
        return self._vector(text)


def document(
    clause_id: str,
    text: str,
    *,
    language: Language = Language.ES,
    jurisdiction: Jurisdiction | None = None,
    version: int = 1,
) -> ClauseDocument:
    """A fixture clause document; the jurisdiction defaults to the id's jurisdiction segment."""
    return ClauseDocument(
        clause_id=clause_id,
        version=version,
        jurisdiction=jurisdiction or Jurisdiction(clause_id.split("-")[1]),
        language=language,
        family=ClauseFamily(clause_id.split("-")[0]),
        text=f"[fixture] {text}",
    )


FIXTURE_DOCUMENTS = (
    document("DSP-MX-1", "plazo para aclarar un cargo de noventa dias en mexico"),
    document("DSP-CO-1", "plazo para presentar una reclamacion en colombia"),
    document("CRD-ALL-2", "bloqueo preventivo de la tarjeta perdida o robada"),
    document("ACC-ALL-1", "saldo de tus cuentas y estado de tus pagos con fecha de corte"),
    document("CRD-ALL-2", "bloqueio preventivo do cartao perdido ou roubado", language=Language.PT),
    document("DSP-MX-1", "prazo para contestar uma cobranca no mexico", language=Language.PT),
)
