"""The filesystem ``ModelRegistry``: versioned JSON artifacts with a digest, and aliases with promotion records.

Layout under the registry root (``WORKFLOW_MODEL_REGISTRY_DIR``, gitignored by default under ``data/``)::

    <component>/<name>/versions/<version>/artifact.json    model parameters only, never customer records
    <component>/<name>/versions/<version>/manifest.json    digest, metadata (metrics, dataset hash, git sha)
    <component>/<name>/aliases/<alias>.json                the version an alias points at, and its promotion record
    <component>/<name>/promotions.jsonl                    every alias move, append only

The version is the first 12 hex digits of the artifact's SHA-256, so an identical retrain yields the same version.
``resolve`` verifies the digest before returning; ``read_verified`` verifies it again when the bytes are read, so a
file swapped between the two calls is refused. Artifacts are JSON and are never unpickled.
``FilesystemModelStore`` is the writer the training CLI (``bank-ml``) uses; the API only reads.
"""

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bank_agent.domain.errors import ModelArtifactIntegrityError, ModelArtifactNotFoundError
from bank_agent.domain.intelligence import ModelComponent, ModelRef, ResolvedArtifact

ARTIFACT_FILE = "artifact.json"
MANIFEST_FILE = "manifest.json"
PROMOTIONS_FILE = "promotions.jsonl"
ALIASES = ("champion", "candidate")
VERSION_LENGTH = 12
_QUALIFIED = re.compile(r"^(?P<component>[a-z_]+):(?P<name>[a-z][a-z0-9_]{0,63})$")
_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def split_name(name: str) -> tuple[ModelComponent, str]:
    """``router:tfidf`` -> (``ModelComponent.ROUTER``, ``tfidf``)."""
    match = _QUALIFIED.fullmatch(name)
    if match is None:
        raise ModelArtifactNotFoundError(f"a registry name has the form component:name, got {name!r}")
    try:
        component = ModelComponent(match["component"])
    except ValueError:
        raise ModelArtifactNotFoundError(f"unknown model component in {name!r}") from None
    return component, match["name"]


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
        Path(temporary).replace(path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ModelArtifactIntegrityError(f"unreadable registry file {path.name}") from error
    if not isinstance(value, dict):
        raise ModelArtifactIntegrityError(f"registry file {path.name} is not an object")
    return value


class FilesystemModelRegistry:
    """Implements ``ModelRegistry`` over the layout above."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def _model_dir(self, name: str) -> tuple[ModelComponent, str, Path]:
        component, short = split_name(name)
        return component, short, self._root / component.value / short

    def resolve(self, name: str, version_or_alias: str) -> ResolvedArtifact:
        component, short, model_dir = self._model_dir(name)
        if not _VERSION.fullmatch(version_or_alias):
            raise ModelArtifactNotFoundError(f"invalid version or alias {version_or_alias!r}")
        version = version_or_alias
        alias_file = model_dir / "aliases" / f"{version_or_alias}.json"
        if alias_file.is_file():
            pointed = _read_json(alias_file).get("version")
            if not isinstance(pointed, str) or not _VERSION.fullmatch(pointed):
                raise ModelArtifactIntegrityError(f"alias {version_or_alias} of {name} names no valid version")
            version = pointed
        version_dir = model_dir / "versions" / version
        artifact, manifest_file = version_dir / ARTIFACT_FILE, version_dir / MANIFEST_FILE
        if not artifact.is_file() or not manifest_file.is_file():
            raise ModelArtifactNotFoundError(f"no artifact for {name}@{version_or_alias}")
        manifest = _read_json(manifest_file)
        expected = manifest.get("sha256")
        if not isinstance(expected, str) or digest(artifact.read_bytes()) != expected:
            raise ModelArtifactIntegrityError(f"the digest of {name}@{version} does not match its manifest")
        metadata = manifest.get("metadata", {})
        return ResolvedArtifact(
            ref=ModelRef(component=component, name=short, version=version),
            local_path=str(artifact),
            sha256=expected,
            metadata=metadata if isinstance(metadata, dict) else {},
        )


def read_verified(artifact: ResolvedArtifact) -> dict[str, Any]:
    """The artifact's JSON object, after checking the bytes against the resolved digest once more."""
    try:
        payload = Path(artifact.local_path).read_bytes()
    except OSError as error:
        raise ModelArtifactNotFoundError(f"artifact {artifact.ref} is not readable") from error
    if digest(payload) != artifact.sha256:
        raise ModelArtifactIntegrityError(f"artifact {artifact.ref} changed after it was resolved")
    try:
        value = json.loads(payload)
    except ValueError as error:
        raise ModelArtifactIntegrityError(f"artifact {artifact.ref} is not valid JSON") from error
    if not isinstance(value, dict):
        raise ModelArtifactIntegrityError(f"artifact {artifact.ref} is not a JSON object")
    return value


def canonical_json(value: Mapping[str, Any]) -> bytes:
    """Sorted keys and no whitespace, so equal parameters always give equal bytes and the same version."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


class FilesystemModelStore:
    """Registers versions and moves aliases in the layout ``FilesystemModelRegistry`` reads (training side)."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self.registry = FilesystemModelRegistry(root)

    def _model_dir(self, name: str) -> Path:
        component, short = split_name(name)
        return self._root / component.value / short

    def register(self, name: str, artifact: Mapping[str, Any], metadata: Mapping[str, Any]) -> ResolvedArtifact:
        """Store ``artifact`` under its content version (idempotent) and return it resolved."""
        payload = canonical_json(artifact)
        sha = digest(payload)
        version_dir = self._model_dir(name) / "versions" / sha[:VERSION_LENGTH]
        _atomic_write(version_dir / ARTIFACT_FILE, payload)
        manifest = {"sha256": sha, "name": name, "metadata": dict(metadata)}
        _atomic_write(version_dir / MANIFEST_FILE, json.dumps(manifest, indent=2, sort_keys=True).encode() + b"\n")
        return self.registry.resolve(name, sha[:VERSION_LENGTH])

    def alias(self, name: str, alias: str) -> dict[str, Any] | None:
        """The alias record (``version`` and the promotion record), or ``None`` when the alias is not set."""
        path = self._model_dir(name) / "aliases" / f"{alias}.json"
        return _read_json(path) if path.is_file() else None

    def set_alias(self, name: str, alias: str, version: str, record: Mapping[str, Any]) -> None:
        """Point ``alias`` at an existing ``version`` and append the move to the promotion history."""
        if alias not in ALIASES:
            raise ModelArtifactNotFoundError(f"unknown alias {alias!r}; use one of {', '.join(ALIASES)}")
        self.registry.resolve(name, version)
        entry = {"alias": alias, "version": version, **dict(record)}
        _atomic_write(
            self._model_dir(name) / "aliases" / f"{alias}.json", json.dumps(entry, indent=2, sort_keys=True).encode()
        )
        self.log_decision(name, entry)

    def log_decision(self, name: str, entry: Mapping[str, Any]) -> None:
        """Append ``entry`` to the promotion history (alias moves and refused promotions alike)."""
        path = self._model_dir(name) / PROMOTIONS_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(dict(entry), sort_keys=True) + "\n")

    def history(self, name: str) -> list[dict[str, Any]]:
        path = self._model_dir(name) / PROMOTIONS_FILE
        if not path.is_file():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
