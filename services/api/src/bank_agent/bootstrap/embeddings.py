"""The hosted embedding gateway for Qdrant retrieval (ADR 0047), assembled from building blocks.

Outermost first: redaction of the query, the port over the backend (batching, unit vectors), cost accounting, the
circuit breaker, bounded retry, and the LiteLLM call with its timeout (``adapters/embeddings/backend.py`` explains
the order). The model, base, and key come from ``RetrievalSettings`` and ``LLMSettings``: one Azure OpenAI account
serves the chat and the embedding deployments, so the embedding call uses ``LLM_API_KEY_PRIMARY``.
"""

from datetime import timedelta

from bank_agent.adapters.embeddings.backend import (
    CircuitBreakingEmbedding,
    CostAccountingEmbedding,
    EmbeddingBackend,
    RetryingEmbedding,
)
from bank_agent.adapters.embeddings.gateway import GatewayEmbedder, RedactingEmbedder
from bank_agent.adapters.embeddings.litellm_embedding import LiteLLMEmbedding
from bank_agent.adapters.llm.prices import PriceTable
from bank_agent.adapters.llm.redaction import Redactor
from bank_agent.bootstrap.settings import LLMSettings, RetrievalSettings
from bank_agent.ports.determinism import Clock
from bank_agent.ports.embeddings import Embedder
from bank_agent.ports.telemetry import Telemetry


def build_embedding_backend(
    retrieval: RetrievalSettings,
    llm: LLMSettings,
    *,
    clock: Clock,
    telemetry: Telemetry,
    provider: EmbeddingBackend | None = None,
) -> EmbeddingBackend:
    """Cost accounting over the circuit breaker over retry over the provider (LiteLLM unless one is injected)."""
    backend: EmbeddingBackend = provider or LiteLLMEmbedding(
        retrieval.hosted_embedding_model,
        api_key=llm.api_key_primary,
        api_base=retrieval.embedding_api_base or llm.api_base or None,
        timeout_seconds=retrieval.embedding_timeout_seconds,
        dimensions=retrieval.hosted_embedding_dimensions,
    )
    backend = RetryingEmbedding(backend, max_retries=retrieval.embedding_max_retries)
    backend = CircuitBreakingEmbedding(
        backend,
        clock=clock,
        failure_threshold=retrieval.embedding_circuit_failure_threshold,
        reset_after=timedelta(seconds=retrieval.embedding_circuit_reset_seconds),
    )
    return CostAccountingEmbedding(backend, prices=PriceTable.from_yaml(llm.prices_file), telemetry=telemetry)


def build_hosted_embedder(
    retrieval: RetrievalSettings,
    llm: LLMSettings,
    *,
    clock: Clock,
    telemetry: Telemetry,
    provider: EmbeddingBackend | None = None,
    redactor: Redactor | None = None,
) -> Embedder:
    backend = build_embedding_backend(retrieval, llm, clock=clock, telemetry=telemetry, provider=provider)
    return RedactingEmbedder(GatewayEmbedder(backend), redactor=redactor or Redactor())
