"""Package contracted local inputs and restore verified archives without replacing existing sources."""

import argparse
import gzip
import hashlib
import io
import json
import shutil
import sys
import tarfile
import tempfile
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from bank_data.config import load_config
from bank_data.contracts.tables import TABLES
from bank_data.ingest.layout import parse_key

MANIFEST = "source-manifest.json"
MAX_BYTES = 20 * 1024**3


class SourceFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    path: str
    bytes: int = Field(ge=0, le=MAX_BYTES)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SourceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1.0.0"] = "1.0.0"
    dataset_version: str
    snapshot_date: date
    code_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    files: list[SourceFile] = Field(min_length=1, max_length=100_000)


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _safe_path(key: str, snapshot: date) -> bool:
    path = PurePosixPath(key)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and path.as_posix() == key
        and parse_key(key, prefix="", snapshot_date=snapshot) is not None
    )


def _manifest(document: bytes) -> SourceManifest:
    manifest = SourceManifest.model_validate_json(document)
    keys = [entry.path for entry in manifest.files]
    if len(keys) != len(set(keys)) or not all(_safe_path(key, manifest.snapshot_date) for key in keys):
        raise ValueError("invalid source paths")
    if sum(entry.bytes for entry in manifest.files) > MAX_BYTES:
        raise ValueError("source exceeds transfer bounds")
    return manifest


def pack(root: Path, archive: Path, revision: str) -> dict[str, str | int]:
    root = root.resolve(strict=True)
    config = load_config(Path(__file__).resolve().parents[2] / "data_platform/config/sources.yml")
    files: list[SourceFile] = []
    for spec in TABLES:
        if spec.layout == "snapshot":
            paths = [root / f"{spec.name}.{suffix}" for suffix in ("csv", "parquet")]
        else:
            paths = sorted(
                path
                for suffix in ("csv", "parquet")
                for path in (root / spec.name).glob(f"year=*/month=*/day=*/*.{suffix}")
            )
        for path in paths:
            if not path.exists():
                continue
            key = path.relative_to(root).as_posix()
            if path.resolve() != path or not path.is_file() or not _safe_path(key, config.dataset.snapshot_date):
                raise ValueError("source contains a link or unsupported object")
            files.append(SourceFile(path=key, bytes=path.stat().st_size, sha256=sha256(path)))
    manifest = SourceManifest(
        dataset_version=config.dataset.version,
        snapshot_date=config.dataset.snapshot_date,
        code_revision=revision,
        files=sorted(files, key=lambda entry: entry.path),
    )
    _manifest(manifest.model_dump_json().encode())
    archive.parent.mkdir(parents=True, exist_ok=True)
    # A complete, immutable archive is installed only after every source stays unchanged.
    with tempfile.TemporaryDirectory(dir=archive.parent) as staging:
        partial = Path(staging) / "source.tar.gz"
        with (
            partial.open("xb") as output,
            gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0, compresslevel=1) as compressed,
            tarfile.open(fileobj=compressed, mode="w|", format=tarfile.USTAR_FORMAT) as bundle,
        ):
            document = manifest.model_dump_json().encode()
            info = tarfile.TarInfo(MANIFEST)
            info.size, info.mode = len(document), 0o600
            bundle.addfile(info, io.BytesIO(document))
            for entry in manifest.files:
                path = root / entry.path
                info = tarfile.TarInfo(entry.path)
                info.size, info.mode = entry.bytes, 0o600
                with path.open("rb") as handle:
                    bundle.addfile(info, handle)
                if sha256(path) != entry.sha256:
                    raise ValueError("source changed during packaging")
        checksum = sha256(partial)
        if archive.exists():
            if sha256(archive) != checksum:
                raise ValueError("refusing to replace a different source archive")
        else:
            partial.replace(archive)
            archive.chmod(0o600)
    return {"sha256": checksum, "objects": len(files), "source_bytes": sum(entry.bytes for entry in files)}


def restore(archive: Path, destination: Path, expected: str) -> dict[str, str | int]:
    if sha256(archive) != expected:
        raise ValueError("source archive SHA-256 mismatch")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        staged = Path(temporary) / "source"
        staged.mkdir(mode=0o700)
        with tarfile.open(archive, mode="r|gz") as bundle:
            first = bundle.next()
            if first is None or first.name != MANIFEST or not first.isfile() or first.size > 16 * 1024**2:
                raise ValueError("missing or invalid source manifest")
            handle = bundle.extractfile(first)
            if handle is None:
                raise ValueError("missing manifest body")
            with handle:
                document = handle.read()
            manifest = _manifest(document)
            entries = {entry.path: entry for entry in manifest.files}
            seen: set[str] = set()
            while member := bundle.next():
                entry = entries.get(member.name)
                if entry is None or member.name in seen or not member.isfile() or member.size != entry.bytes:
                    raise ValueError("unexpected or invalid source member")
                target = staged / entry.path
                target.parent.mkdir(parents=True, exist_ok=True)
                handle = bundle.extractfile(member)
                if handle is None:
                    raise ValueError("missing source body")
                with handle, target.open("xb") as output:
                    shutil.copyfileobj(handle, output, length=1024 * 1024)
                target.chmod(0o600)
                if sha256(target) != entry.sha256:
                    raise ValueError("source member SHA-256 mismatch")
                seen.add(member.name)
            if seen != set(entries):
                raise ValueError("incomplete source archive")
        (staged / MANIFEST).write_bytes(document)
        (staged / MANIFEST).chmod(0o600)
        if destination.exists():
            existing = destination / MANIFEST
            if (
                destination.is_symlink()
                or existing.is_symlink()
                or not existing.is_file()
                or existing.read_bytes() != document
            ):
                raise ValueError("refusing to replace existing source")
            expected_paths = set(entries) | {MANIFEST}
            actual_paths = {
                path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file()
            }
            if actual_paths != expected_paths or any(
                (destination / entry.path).resolve() != destination.absolute() / entry.path
                or sha256(destination / entry.path) != entry.sha256
                for entry in manifest.files
            ):
                raise ValueError("existing source differs from archive")
        else:
            staged.rename(destination)
    return {"sha256": expected, "objects": len(entries), "source_bytes": sum(entry.bytes for entry in entries.values())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("pack", "restore"))
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("digest_or_revision")
    args = parser.parse_args()
    try:
        result = (
            pack(args.input, args.output, args.digest_or_revision)
            if args.action == "pack"
            else restore(args.input, args.output, args.digest_or_revision)
        )
    except (OSError, ValueError, tarfile.TarError) as error:
        sys.stderr.write(f"Source transfer failed ({type(error).__name__}); no input records logged.\n")
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
