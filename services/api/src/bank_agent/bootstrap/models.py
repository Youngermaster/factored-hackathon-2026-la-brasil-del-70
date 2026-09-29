"""Selects the router, resolver, and risk estimator implementations named in ``WorkflowSettings``, loading learned
artifacts through the filesystem ``ModelRegistry`` by version or alias.

``keyword@1``, ``rules@1``, and ``score_band@1`` are the baselines. ``tfidf@<version or alias>``,
``embeddings@<...>``, ``lgbm@<...>`` (resolver or risk estimator), and ``logreg@<...>`` load registered artifacts.

Degradation level L3 (``docs/operations/degradation.md``): when a learned model cannot load (no artifact, the
``ml`` extra absent, or the registry unreadable), the baseline serves, a structured warning names the reason, and
``ModelFallbacks.served_baseline`` records the component so the degradation monitor reports L3. A router that fell
back uses the stricter keyword threshold (``DEGRADATION_ROUTER_THRESHOLD``). A risk estimator that cannot load is
replaced by ``score_band@1`` only when ``DEGRADATION_RISK_BAND_FALLBACK=true``; otherwise every estimate is
unavailable and the synthetic eligibility service sends the request to human review. With
``DEGRADATION_MODEL_BASELINES=false`` a load failure stops startup instead. A digest mismatch or a malformed artifact
is never tolerated at any level: it stops startup, because a tampered model is not an availability problem.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from bank_agent.adapters.models.embedding_router import EmbeddingIntentRouter
from bank_agent.adapters.models.keyword_router import KeywordIntentRouter
from bank_agent.adapters.models.learned_risk import LearnedRiskEstimator
from bank_agent.adapters.models.lgbm_resolver import LgbmTransactionResolver
from bank_agent.adapters.models.registry import FilesystemModelRegistry
from bank_agent.adapters.models.rules_resolver import RuleTransactionResolver
from bank_agent.adapters.models.score_band_risk import ScoreBandRiskEstimator
from bank_agent.adapters.models.tfidf_router import TfidfIntentRouter
from bank_agent.adapters.models.unavailable_risk import UnavailableRiskEstimator
from bank_agent.adapters.retrieval.embedding import Embedder, ml_extra_installed
from bank_agent.bootstrap.retrieval import build_embedder
from bank_agent.bootstrap.settings import RetrievalSettings, WorkflowSettings
from bank_agent.domain.errors import ConfigurationError, ModelArtifactNotFoundError, ModelUnavailableError
from bank_agent.ports.determinism import Clock, IdGenerator
from bank_agent.ports.models import IntentRouter, ModelRegistry, RiskEstimator, TransactionResolver

_log = structlog.get_logger(__name__)
EmbedderFactory = Callable[[], Embedder | None]
LOAD_FAILURES = (ModelArtifactNotFoundError, ModelUnavailableError, OSError)
"""Availability failures (L3). ``ModelArtifactIntegrityError`` is deliberately absent: it stops startup."""


@dataclass
class ModelFallbacks:
    """The L3 options (``DEGRADATION_*``) and the components that serve a baseline after a failed load."""

    baselines_allowed: bool = True
    router_threshold: float | None = None
    risk_band_fallback: bool = False
    served_baseline: list[str] = field(default_factory=list)

    def fell_back(self, component: str, selection: str, error: Exception) -> None:
        if not self.baselines_allowed:
            raise ConfigurationError(f"{selection} cannot load and DEGRADATION_MODEL_BASELINES is off") from error
        self.served_baseline.append(component)

    def keyword_router(self) -> KeywordIntentRouter:
        if self.router_threshold is None:
            return KeywordIntentRouter()
        return KeywordIntentRouter(threshold=self.router_threshold)


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
    settings: WorkflowSettings,
    registry: ModelRegistry,
    embedder: EmbedderFactory | None = None,
    fallbacks: ModelFallbacks | None = None,
) -> IntentRouter:
    fallbacks = fallbacks or ModelFallbacks()
    name, version = split_selection(settings.router)
    if name == "keyword":
        return KeywordIntentRouter()
    try:
        resolved = registry.resolve(f"router:{name}", version)
        if name == "tfidf":
            return TfidfIntentRouter.load(resolved)
        return EmbeddingIntentRouter.load(resolved, embedder() if embedder is not None else None)
    except LOAD_FAILURES as error:
        fallbacks.fell_back("router", settings.router, error)
        _fallback("router", settings.router, type(error).__name__, "router:keyword@1")
        return fallbacks.keyword_router()


def build_resolver(
    settings: WorkflowSettings, registry: ModelRegistry, fallbacks: ModelFallbacks | None = None
) -> TransactionResolver:
    fallbacks = fallbacks or ModelFallbacks()
    name, version = split_selection(settings.resolver)
    if name == "rules":
        return RuleTransactionResolver()
    try:
        return LgbmTransactionResolver.load(registry.resolve(f"resolver:{name}", version))
    except LOAD_FAILURES as error:
        fallbacks.fell_back("resolver", settings.resolver, error)
        _fallback("resolver", settings.resolver, type(error).__name__, "resolver:rules@1")
        return RuleTransactionResolver()


def build_risk_estimator(
    settings: WorkflowSettings,
    registry: ModelRegistry,
    clock: Clock,
    ids: IdGenerator,
    fallbacks: ModelFallbacks | None = None,
) -> RiskEstimator:
    """The selected estimator. One that cannot load serves ``score_band@1`` only when the flag allows it, otherwise
    none (every eligibility request goes to review); a corrupt one stops startup; an estimate that cannot be
    computed raises ``risk_estimator_unavailable``."""
    fallbacks = fallbacks or ModelFallbacks()
    name, version = split_selection(settings.risk_estimator)
    if name == "score_band":
        return ScoreBandRiskEstimator(clock, ids)
    try:
        return LearnedRiskEstimator.load(registry.resolve(f"risk_estimator:{name}", version), clock, ids)
    except LOAD_FAILURES as error:
        fallbacks.fell_back("risk_estimator", settings.risk_estimator, error)
        if fallbacks.risk_band_fallback:
            _fallback("risk_estimator", settings.risk_estimator, type(error).__name__, "risk_estimator:score_band@1")
            return ScoreBandRiskEstimator(clock, ids)
        _fallback("risk_estimator", settings.risk_estimator, type(error).__name__, "none, review required")
        return UnavailableRiskEstimator(settings.risk_estimator)


def build_model_registry(root: Path) -> ModelRegistry:
    return FilesystemModelRegistry(root)
