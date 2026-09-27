"""The filesystem model registry: content versions, aliases, promotion history, and integrity checks."""

import json
from pathlib import Path

import pytest

from bank_agent.adapters.models.registry import (
    FilesystemModelRegistry,
    FilesystemModelStore,
    canonical_json,
    digest,
    read_verified,
    split_name,
)
from bank_agent.domain.errors import ModelArtifactIntegrityError, ModelArtifactNotFoundError
from bank_agent.domain.intelligence import ModelComponent
from bank_agent_models import TFIDF_ARTIFACT, publish


def test_the_version_is_the_content_digest_so_a_retrain_is_idempotent(tmp_path: Path) -> None:
    store = FilesystemModelStore(tmp_path)
    first = store.register("router:tfidf", TFIDF_ARTIFACT, {"run": 1})
    second = store.register("router:tfidf", dict(TFIDF_ARTIFACT), {"run": 2})
    assert first.ref.version == second.ref.version == digest(canonical_json(TFIDF_ARTIFACT))[:12]
    assert str(first.ref) == f"router:tfidf@{first.ref.version}"
    assert second.metadata == {"run": 2}


def test_aliases_resolve_to_their_version_and_every_move_is_recorded(tmp_path: Path) -> None:
    resolved = publish(tmp_path, "router:tfidf", TFIDF_ARTIFACT, alias="candidate")
    store = FilesystemModelStore(tmp_path)
    store.set_alias("router:tfidf", "champion", resolved.ref.version, {"approved_by": "reviewer"})
    registry = FilesystemModelRegistry(tmp_path)
    assert registry.resolve("router:tfidf", "champion").ref == resolved.ref
    assert registry.resolve("router:tfidf", "candidate").sha256 == resolved.sha256
    assert [entry["alias"] for entry in store.history("router:tfidf")] == ["candidate", "champion"]
    alias = store.alias("router:tfidf", "champion")
    assert alias is not None
    assert alias["approved_by"] == "reviewer"
    assert store.alias("router:tfidf", "missing") is None
    assert store.history("resolver:lgbm") == []


def test_unknown_names_versions_and_aliases_are_not_found(tmp_path: Path) -> None:
    registry = FilesystemModelRegistry(tmp_path)
    for name, version in (("router:tfidf", "champion"), ("router:tfidf", "abc"), ("router", "1"), ("nope:x", "1")):
        with pytest.raises(ModelArtifactNotFoundError):
            registry.resolve(name, version)
    with pytest.raises(ModelArtifactNotFoundError):
        registry.resolve("router:tfidf", "../escape")
    with pytest.raises(ModelArtifactNotFoundError):
        FilesystemModelStore(tmp_path).set_alias("router:tfidf", "production", "abc", {})


def test_a_tampered_artifact_fails_the_digest_check(tmp_path: Path) -> None:
    resolved = publish(tmp_path, "router:tfidf", TFIDF_ARTIFACT)
    Path(resolved.local_path).write_text(json.dumps({**TFIDF_ARTIFACT, "threshold": 0.1}))
    with pytest.raises(ModelArtifactIntegrityError):
        FilesystemModelRegistry(tmp_path).resolve("router:tfidf", "champion")
    with pytest.raises(ModelArtifactIntegrityError):
        read_verified(resolved)


def test_a_broken_alias_or_manifest_is_an_integrity_error(tmp_path: Path) -> None:
    resolved = publish(tmp_path, "router:tfidf", TFIDF_ARTIFACT)
    model_dir = tmp_path / "router" / "tfidf"
    (model_dir / "aliases" / "champion.json").write_text(json.dumps({"version": 7}))
    with pytest.raises(ModelArtifactIntegrityError):
        FilesystemModelRegistry(tmp_path).resolve("router:tfidf", "champion")
    (model_dir / "versions" / resolved.ref.version / "manifest.json").write_text("[1]")
    with pytest.raises(ModelArtifactIntegrityError):
        FilesystemModelRegistry(tmp_path).resolve("router:tfidf", resolved.ref.version)


def test_read_verified_refuses_missing_and_non_object_payloads(tmp_path: Path) -> None:
    resolved = publish(tmp_path, "router:tfidf", TFIDF_ARTIFACT)
    assert read_verified(resolved)["format"] == "tfidf_logreg/1"
    array = tmp_path / "array.json"
    array.write_bytes(b"[1]")
    with pytest.raises(ModelArtifactIntegrityError):
        read_verified(resolved.model_copy(update={"local_path": str(array), "sha256": digest(b"[1]")}))
    garbage = tmp_path / "garbage.json"
    garbage.write_bytes(b"{")
    with pytest.raises(ModelArtifactIntegrityError):
        read_verified(resolved.model_copy(update={"local_path": str(garbage), "sha256": digest(b"{")}))
    with pytest.raises(ModelArtifactNotFoundError):
        read_verified(resolved.model_copy(update={"local_path": str(tmp_path / "gone.json")}))


def test_split_name_parses_the_component() -> None:
    assert split_name("resolver:lgbm") == (ModelComponent.RESOLVER, "lgbm")
