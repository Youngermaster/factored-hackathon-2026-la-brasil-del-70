"""Selects the router and resolver implementations named in ``WorkflowSettings``, loading learned artifacts
through the filesystem ``ModelRegistry`` by version or alias.

``keyword@1`` and ``rules@1`` are the rule baselines. ``tfidf@<version or alias>``, ``embeddings@<...>``, and
``lgbm@<...>`` load registered artifacts. When no artifact exists for the name (a fresh checkout before
``make train``), or the embeddings router cannot run because the ``ml`` extra is absent, the baseline serves and a
structured warning names the reason; every prediction still records the model that actually answered. A digest
mismatch or a malformed artifact is never tolerated: it stops startup.
"""

from collections.abc import Callable
from pathlib import Path

import structlog

from bank_agent.adapters.models.embedding_router import EmbeddingIntentRouter
from bank_agent.adapters.models.keyword_router import KeywordIntentRouter
from bank_agent.adapters.models.lgbm_resolver import LgbmTransactionResolver
from bank_agent.adapters.models.registry import FilesystemModelRegistry
from bank_agent.adapters.models.rules_resolver import RuleTransactionResolver
from bank_agent.adapters.models.tfidf_router import TfidfIntentRouter
from bank_agent.adapters.retrieval.embedding import Embedder, ml_extra_installed
from bank_agent.bootstrap.retrieval import build_embedder
from bank_agent.bootstrap.settings import RetrievalSettings, WorkflowSettings
from bank_agent.domain.errors import ConfigurationError, ModelArtifactNotFoundError, ModelUnavailableError
from bank_agent.ports.models import IntentRouter, ModelRegistry, TransactionResolver

_log = structlog.get_logger(__name__)
EmbedderFactory = Callable[[], Embedder | None]


def split_selection(value: str) -> tuple[str, str]:
    name, separator, version = value.partition("@")
    if not separator or not name or not version:
        raise ConfigurationError(f"a model selection has the form name@version_or_alias, got {value!r}")
    return name, version


def default_embedder(retrieval: RetrievalSettings) -> EmbedderFactory:
    def factory() -> Embedder | None:
        if not ml_extra_installed():
            return None
        return build_embedder(
            retrieval.embedding_model,
            model_cache_dir=retrieval.model_cache_dir,
            embedding_cache_dir=retrieval.embedding_cache_dir,
        )

    return factory


def _fallback(component: str, selection: str, reason: str, baseline: str) -> None:
    _log.warning("model_fallback", component=component, selected=selection, served=baseline, reason=reason)


def build_router(
    settings: WorkflowSettings, registry: ModelRegistry, embedder: EmbedderFactory | None = None
) -> IntentRouter:
    name, version = split_selection(settings.router)
    if name == "keyword":
        return KeywordIntentRouter()
    try:
        resolved = registry.resolve(f"router:{name}", version)
        if name == "tfidf":
            return TfidfIntentRouter.load(resolved)
        return EmbeddingIntentRouter.load(resolved, embedder() if embedder is not None else None)
    except (ModelArtifactNotFoundError, ModelUnavailableError) as error:
        _fallback("router", settings.router, str(error), "router:keyword@1")
        return KeywordIntentRouter()


def build_resolver(settings: WorkflowSettings, registry: ModelRegistry) -> TransactionResolver:
    name, version = split_selection(settings.resolver)
    if name == "rules":
        return RuleTransactionResolver()
    try:
        return LgbmTransactionResolver.load(registry.resolve(f"resolver:{name}", version))
    except ModelArtifactNotFoundError as error:
        _fallback("resolver", settings.resolver, str(error), "resolver:rules@1")
        return RuleTransactionResolver()


def build_model_registry(root: Path) -> ModelRegistry:
    return FilesystemModelRegistry(root)
