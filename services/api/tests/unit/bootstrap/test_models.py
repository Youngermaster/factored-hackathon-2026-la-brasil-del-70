"""Model selection in the composition root: baselines, registry loads by alias, and the documented fallbacks."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from bank_agent.adapters.models.embedding_router import EmbeddingIntentRouter
from bank_agent.adapters.models.keyword_router import KeywordIntentRouter
from bank_agent.adapters.models.lgbm_resolver import LgbmTransactionResolver
from bank_agent.adapters.models.rules_resolver import RuleTransactionResolver
from bank_agent.adapters.models.tfidf_router import TfidfIntentRouter
from bank_agent.bootstrap.models import (
    build_model_registry,
    build_resolver,
    build_router,
    default_embedder,
    split_selection,
)
from bank_agent.bootstrap.settings import DEFAULT_MODEL_REGISTRY_DIR, RetrievalSettings, WorkflowSettings
from bank_agent.domain.errors import ConfigurationError, ModelArtifactIntegrityError
from bank_agent_models import EMBEDDING_ARTIFACT, LGBM_ARTIFACT, TFIDF_ARTIFACT, FixtureEmbedder, publish


def settings(tmp_path: Path, **values: str) -> WorkflowSettings:
    return WorkflowSettings.model_validate({"model_registry_dir": tmp_path, **values})


def test_defaults_are_the_rule_baselines(tmp_path: Path) -> None:
    defaults = WorkflowSettings()
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
            WorkflowSettings.model_validate({field: value})
    blank = WorkflowSettings.model_validate({"router": " ", "resolver": "", "model_registry_dir": ""})
    assert (blank.router, blank.resolver, blank.model_registry_dir) == (
        "keyword@1",
        "rules@1",
        DEFAULT_MODEL_REGISTRY_DIR,
    )


def test_default_embedder_is_absent_without_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("bank_agent.bootstrap.models.ml_extra_installed", lambda: False)
    assert default_embedder(RetrievalSettings())() is None


def test_default_embedder_builds_the_cached_sentence_transformer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("bank_agent.bootstrap.models.ml_extra_installed", lambda: True)
    built: list[str] = []

    def fake_build(name: str, **_: object) -> FixtureEmbedder:
        built.append(name)
        return FixtureEmbedder()

    monkeypatch.setattr("bank_agent.bootstrap.models.build_embedder", fake_build)
    assert isinstance(default_embedder(RetrievalSettings())(), FixtureEmbedder)
    assert built == [RetrievalSettings().embedding_model]
