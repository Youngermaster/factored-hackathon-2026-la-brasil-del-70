"""Model selection in the composition root: baselines, registry loads by alias, and the documented fallbacks."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from bank_agent.adapters.models.embedding_router import EmbeddingIntentRouter
from bank_agent.adapters.models.keyword_router import KeywordIntentRouter
from bank_agent.adapters.models.learned_risk import LearnedRiskEstimator
from bank_agent.adapters.models.lgbm_resolver import LgbmTransactionResolver
from bank_agent.adapters.models.rules_resolver import RuleTransactionResolver
from bank_agent.adapters.models.score_band_risk import ScoreBandRiskEstimator
from bank_agent.adapters.models.tfidf_router import TfidfIntentRouter
from bank_agent.adapters.models.unavailable_risk import UnavailableRiskEstimator
from bank_agent.bootstrap.models import (
    ModelFallbacks,
    build_model_registry,
    build_resolver,
    build_risk_estimator,
    build_router,
    default_embedder,
    split_selection,
)
from bank_agent.bootstrap.settings import DEFAULT_MODEL_REGISTRY_DIR, RetrievalSettings, WorkflowSettings
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.credit import CreditProductType
from bank_agent.domain.eligibility import CreditRiskFeatures
from bank_agent.domain.errors import ConfigurationError, ModelArtifactIntegrityError, RiskEstimatorUnavailableError
from bank_agent.domain.locale import Country, Language
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.ids import SequentialIdGenerator
from bank_agent_builders import T0
from bank_agent_models import (
    EMBEDDING_ARTIFACT,
    LGBM_ARTIFACT,
    RISK_LGBM_ARTIFACT,
    RISK_LOGREG_ARTIFACT,
    TFIDF_ARTIFACT,
    FixtureEmbedder,
    publish,
)

FEATURES = CreditRiskFeatures(
    jurisdiction=Country.MX, product_type=CreditProductType.PERSONAL_LOAN, requested_term_months=24, credit_score=700
)


@pytest.fixture(autouse=True)
def _no_model_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    names = ("WORKFLOW_ROUTER", "WORKFLOW_RESOLVER", "WORKFLOW_RISK_ESTIMATOR", "WORKFLOW_MODEL_REGISTRY_DIR",
             "RETRIEVAL_EMBEDDING_MODEL")  # fmt: skip
    for name in names:
        monkeypatch.delenv(name, raising=False)


def workflow_settings(**values: object) -> WorkflowSettings:
    """Settings from ``values`` and defaults only: no environment file is read."""
    return WorkflowSettings(_env_file=None, **values)  # type: ignore[arg-type]


def settings(tmp_path: Path, **values: str) -> WorkflowSettings:
    return workflow_settings(model_registry_dir=tmp_path, **values)


def test_defaults_are_the_rule_baselines(tmp_path: Path) -> None:
    defaults = workflow_settings()
    assert (defaults.router, defaults.resolver, defaults.model_registry_dir) == (
        "keyword@1",
        "rules@1",
        DEFAULT_MODEL_REGISTRY_DIR,
    )
    registry = build_model_registry(tmp_path)
    assert isinstance(build_router(settings(tmp_path), registry), KeywordIntentRouter)
    assert isinstance(build_resolver(settings(tmp_path), registry), RuleTransactionResolver)


def test_learned_models_load_by_alias(tmp_path: Path) -> None:
    publish(tmp_path, "router:tfidf", TFIDF_ARTIFACT)
    publish(tmp_path, "router:embeddings", EMBEDDING_ARTIFACT)
    publish(tmp_path, "resolver:lgbm", LGBM_ARTIFACT)
    registry = build_model_registry(tmp_path)
    assert isinstance(build_router(settings(tmp_path, router="tfidf@champion"), registry), TfidfIntentRouter)
    embedding = build_router(settings(tmp_path, router="embeddings@champion"), registry, FixtureEmbedder)
    assert isinstance(embedding, EmbeddingIntentRouter)
    resolver = build_resolver(settings(tmp_path, resolver="lgbm@champion"), registry)
    assert isinstance(resolver, LgbmTransactionResolver)


def test_a_missing_artifact_or_extra_falls_back_to_the_baseline(tmp_path: Path) -> None:
    registry = build_model_registry(tmp_path)
    assert isinstance(build_router(settings(tmp_path, router="tfidf@champion"), registry), KeywordIntentRouter)
    assert isinstance(build_resolver(settings(tmp_path, resolver="lgbm@champion"), registry), RuleTransactionResolver)
    publish(tmp_path, "router:embeddings", EMBEDDING_ARTIFACT)
    fallback = build_router(settings(tmp_path, router="embeddings@champion"), registry, lambda: None)
    assert isinstance(fallback, KeywordIntentRouter)
    assert isinstance(build_router(settings(tmp_path, router="embeddings@champion"), registry), KeywordIntentRouter)


def test_a_tampered_artifact_stops_startup(tmp_path: Path) -> None:
    resolved = publish(tmp_path, "router:tfidf", TFIDF_ARTIFACT)
    Path(resolved.local_path).write_text("{}")
    with pytest.raises(ModelArtifactIntegrityError):
        build_router(settings(tmp_path, router="tfidf@champion"), build_model_registry(tmp_path))


def test_selections_are_validated() -> None:
    assert split_selection("tfidf@champion") == ("tfidf", "champion")
    with pytest.raises(ConfigurationError):
        split_selection("tfidf")
    for field, value in (("router", "gpt@1"), ("router", "tfidf@"), ("resolver", "lgbm@../x"), ("resolver", "x@1")):
        with pytest.raises(ValidationError):
            workflow_settings(**{field: value})
    blank = workflow_settings(router=" ", resolver="", model_registry_dir="")
    assert (blank.router, blank.resolver, blank.model_registry_dir) == (
        "keyword@1",
        "rules@1",
        DEFAULT_MODEL_REGISTRY_DIR,
    )


def test_default_embedder_is_absent_without_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("bank_agent.bootstrap.models.ml_extra_installed", lambda: False)
    assert default_embedder(RetrievalSettings(_env_file=None))() is None


def test_default_embedder_builds_the_cached_sentence_transformer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("bank_agent.bootstrap.models.ml_extra_installed", lambda: True)
    built: list[str] = []

    def fake_build(name: str, **_: object) -> FixtureEmbedder:
        built.append(name)
        return FixtureEmbedder()

    monkeypatch.setattr("bank_agent.bootstrap.models.build_embedder", fake_build)
    assert isinstance(default_embedder(RetrievalSettings(_env_file=None))(), FixtureEmbedder)
    assert built == [RetrievalSettings(_env_file=None).embedding_model]


def _risk(tmp_path: Path, selection: str) -> object:
    registry = build_model_registry(tmp_path)
    return build_risk_estimator(
        settings(tmp_path, risk_estimator=selection), registry, FixedClock(T0), SequentialIdGenerator()
    )


def test_the_risk_estimator_defaults_to_the_score_band_baseline(tmp_path: Path) -> None:
    assert workflow_settings().risk_estimator == "score_band@1"
    assert isinstance(_risk(tmp_path, "score_band@1"), ScoreBandRiskEstimator)
    assert workflow_settings(risk_estimator=" ").risk_estimator == "score_band@1"


def test_learned_risk_estimators_load_by_alias(tmp_path: Path) -> None:
    publish(tmp_path, "risk_estimator:logreg", RISK_LOGREG_ARTIFACT)
    publish(tmp_path, "risk_estimator:lgbm", RISK_LGBM_ARTIFACT)
    for name in ("logreg", "lgbm"):
        loaded = _risk(tmp_path, f"{name}@champion")
        assert isinstance(loaded, LearnedRiskEstimator)
        assert loaded.model.name == name


def test_a_missing_risk_artifact_serves_no_estimate_and_a_tampered_one_stops_startup(tmp_path: Path) -> None:
    fallbacks = ModelFallbacks()
    registry = build_model_registry(tmp_path)
    served = build_risk_estimator(
        settings(tmp_path, risk_estimator="lgbm@champion"), registry, FixedClock(T0), SequentialIdGenerator(), fallbacks
    )
    assert isinstance(served, UnavailableRiskEstimator)
    with pytest.raises(RiskEstimatorUnavailableError):
        served.estimate(FEATURES)
    assert fallbacks.served_baseline == ["risk_estimator"]
    resolved = publish(tmp_path, "risk_estimator:lgbm", RISK_LGBM_ARTIFACT)
    Path(resolved.local_path).write_text("{}")
    with pytest.raises(ModelArtifactIntegrityError):
        _risk(tmp_path, "lgbm@champion")


def test_the_score_band_serves_a_missing_risk_artifact_only_when_the_flag_allows_it(tmp_path: Path) -> None:
    fallbacks = ModelFallbacks(risk_band_fallback=True)
    served = build_risk_estimator(
        settings(tmp_path, risk_estimator="logreg@champion"),
        build_model_registry(tmp_path),
        FixedClock(T0),
        SequentialIdGenerator(),
        fallbacks,
    )
    assert isinstance(served, ScoreBandRiskEstimator)
    assert fallbacks.served_baseline == ["risk_estimator"]


def test_a_failed_learned_router_serves_the_stricter_keyword_router_and_is_reported(tmp_path: Path) -> None:
    fallbacks = ModelFallbacks(router_threshold=0.75)
    router = build_router(settings(tmp_path, router="tfidf@champion"), build_model_registry(tmp_path), None, fallbacks)
    assert isinstance(router, KeywordIntentRouter)
    assert router.route(UntrustedText("hola"), Language.ES).below_threshold
    build_resolver(settings(tmp_path, resolver="lgbm@champion"), build_model_registry(tmp_path), fallbacks)
    assert fallbacks.served_baseline == ["router", "resolver"]


def test_an_unreadable_registry_is_an_availability_failure(tmp_path: Path) -> None:
    class Unreadable:
        def resolve(self, name: str, version_or_alias: str) -> object:
            raise PermissionError("registry storage unavailable")

    fallbacks = ModelFallbacks()
    router = build_router(settings(tmp_path, router="tfidf@champion"), Unreadable(), None, fallbacks)  # type: ignore[arg-type]
    assert isinstance(router, KeywordIntentRouter)
    assert fallbacks.served_baseline == ["router"]


def test_without_the_baselines_flag_a_load_failure_stops_startup(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="DEGRADATION_MODEL_BASELINES"):
        build_router(
            settings(tmp_path, router="tfidf@champion"),
            build_model_registry(tmp_path),
            None,
            ModelFallbacks(baselines_allowed=False),
        )


@pytest.mark.parametrize("value", ["score_band@2", "gbm@1", "lgbm@", "logreg@../x"])
def test_risk_estimator_selections_are_validated(value: str) -> None:
    with pytest.raises(ValidationError):
        workflow_settings(risk_estimator=value)
