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

``ModelFallbacks.served`` also records, per component, the model each build actually serves (a concrete version,
never an alias), its kind, and the fallback reason code, for the model inventory (``bootstrap/inventory.py``).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from bank_agent.adapters.models.embedding_router import EmbeddingIntentRouter
from bank_agent.adapters.models.keyword_router import KEYWORD_ROUTER, KeywordIntentRouter
from bank_agent.adapters.models.learned_risk import LearnedRiskEstimator
from bank_agent.adapters.models.lexical_language import LEXICAL_DETECTOR
from bank_agent.adapters.models.lgbm_resolver import LgbmTransactionResolver
from bank_agent.adapters.models.registry import FilesystemModelRegistry
from bank_agent.adapters.models.rules_resolver import RULES_RESOLVER, RuleTransactionResolver
from bank_agent.adapters.models.score_band_risk import SCORE_BAND_ESTIMATOR, ScoreBandRiskEstimator
from bank_agent.adapters.models.tfidf_router import TfidfIntentRouter
from bank_agent.adapters.models.unavailable_risk import UnavailableRiskEstimator
from bank_agent.adapters.retrieval.bm25 import BM25_MODEL
from bank_agent.adapters.retrieval.embedding import Embedder, ml_extra_installed
from bank_agent.bootstrap.retrieval import build_embedder
from bank_agent.bootstrap.settings import RetrievalSettings, WorkflowSettings
from bank_agent.domain.errors import ConfigurationError, ModelArtifactNotFoundError, ModelUnavailableError
from bank_agent.domain.intelligence import ModelComponent, ModelRef
from bank_agent.domain.model_inventory import FallbackReason, ModelKind, ServedModel
from bank_agent.ports.determinism import Clock, IdGenerator
from bank_agent.ports.models import IntentRouter, ModelRegistry, RiskEstimator, TransactionResolver

_log = structlog.get_logger(__name__)
EmbedderFactory = Callable[[], Embedder | None]
LOAD_FAILURES = (ModelArtifactNotFoundError, ModelUnavailableError, OSError)
"""Availability failures (L3). ``ModelArtifactIntegrityError`` is deliberately absent: it stops startup."""
BASELINES = frozenset({KEYWORD_ROUTER, RULES_RESOLVER, SCORE_BAND_ESTIMATOR, BM25_MODEL, LEXICAL_DETECTOR})
"""Rule-based or lexical implementations; every other served model was trained (``learned``)."""


def fallback_reason(error: Exception) -> FallbackReason:
    """The reason code of a load failure; never its message, which may name a path."""
    if isinstance(error, ModelArtifactNotFoundError):
        return "artifact_not_found"
    if isinstance(error, ModelUnavailableError):
        return "model_unavailable"
    return "registry_unreadable"


def served_model(
    component: ModelComponent, selection: str, model: ModelRef | None, error: Exception | None = None
) -> ServedModel:
    """What a component serves: a baseline, a learned model at its concrete version, or nothing."""
    _, version = split_selection(selection)
    alias = version if model is not None and model.version != version and model not in BASELINES else None
    kind: ModelKind = "unavailable" if model is None else "baseline" if model in BASELINES else "learned"
    return ServedModel(
        component=component,
        selected=selection,
        served=model,
        kind=kind,
        alias=alias,
        fell_back=error is not None,
        reason=fallback_reason(error) if error is not None else None,
    )


@dataclass
class ModelFallbacks:
    """The L3 options (``DEGRADATION_*``) and the components that serve a baseline after a failed load."""

    baselines_allowed: bool = True
    router_threshold: float | None = None
    risk_band_fallback: bool = False
    served_baseline: list[str] = field(default_factory=list)
    served: dict[ModelComponent, ServedModel] = field(default_factory=dict)

    def record(
        self, component: ModelComponent, selection: str, model: ModelRef | None, error: Exception | None = None
    ) -> None:
        """Remember what ``component`` serves after its build (the last build wins)."""
        self.served[component] = served_model(component, selection, model, error)

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
        fallbacks.record(ModelComponent.ROUTER, settings.router, KEYWORD_ROUTER)
        return KeywordIntentRouter()
    try:
        resolved = registry.resolve(f"router:{name}", version)
        router: IntentRouter
        if name == "tfidf":
            router = TfidfIntentRouter.load(resolved)
        else:
            router = EmbeddingIntentRouter.load(resolved, embedder() if embedder is not None else None)
    except LOAD_FAILURES as error:
        fallbacks.fell_back("router", settings.router, error)
        fallbacks.record(ModelComponent.ROUTER, settings.router, KEYWORD_ROUTER, error)
        _fallback("router", settings.router, type(error).__name__, "router:keyword@1")
        return fallbacks.keyword_router()
    fallbacks.record(ModelComponent.ROUTER, settings.router, resolved.ref)
    return router


def build_resolver(
    settings: WorkflowSettings, registry: ModelRegistry, fallbacks: ModelFallbacks | None = None
) -> TransactionResolver:
    fallbacks = fallbacks or ModelFallbacks()
    name, version = split_selection(settings.resolver)
    if name == "rules":
        fallbacks.record(ModelComponent.RESOLVER, settings.resolver, RULES_RESOLVER)
        return RuleTransactionResolver()
    try:
        resolved = registry.resolve(f"resolver:{name}", version)
        resolver = LgbmTransactionResolver.load(resolved)
    except LOAD_FAILURES as error:
        fallbacks.fell_back("resolver", settings.resolver, error)
        fallbacks.record(ModelComponent.RESOLVER, settings.resolver, RULES_RESOLVER, error)
        _fallback("resolver", settings.resolver, type(error).__name__, "resolver:rules@1")
        return RuleTransactionResolver()
    fallbacks.record(ModelComponent.RESOLVER, settings.resolver, resolved.ref)
    return resolver


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
    selection = settings.risk_estimator
    if name == "score_band":
        fallbacks.record(ModelComponent.RISK_ESTIMATOR, selection, SCORE_BAND_ESTIMATOR)
        return ScoreBandRiskEstimator(clock, ids)
    try:
        resolved = registry.resolve(f"risk_estimator:{name}", version)
        estimator = LearnedRiskEstimator.load(resolved, clock, ids)
    except LOAD_FAILURES as error:
        fallbacks.fell_back("risk_estimator", selection, error)
        if fallbacks.risk_band_fallback:
            fallbacks.record(ModelComponent.RISK_ESTIMATOR, selection, SCORE_BAND_ESTIMATOR, error)
            _fallback("risk_estimator", selection, type(error).__name__, "risk_estimator:score_band@1")
            return ScoreBandRiskEstimator(clock, ids)
        fallbacks.record(ModelComponent.RISK_ESTIMATOR, selection, None, error)
        _fallback("risk_estimator", selection, type(error).__name__, "none, review required")
        return UnavailableRiskEstimator(selection)
    fallbacks.record(ModelComponent.RISK_ESTIMATOR, selection, resolved.ref)
    return estimator


def build_model_registry(root: Path) -> ModelRegistry:
    return FilesystemModelRegistry(root)
