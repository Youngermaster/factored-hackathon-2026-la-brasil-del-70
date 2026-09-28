"""``LocalSource``: a directory laid out like the bucket prefix, for tests, the committed sample, and offline work."""

import hashlib
import shutil
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

from bank_data.contracts.tables import TABLES
from bank_data.errors import ConfigurationError, SourceAccessError
from bank_data.ingest.layout import parse_key
from bank_data.ingest.source import SourceObject
from bank_data.settings import REPOSITORY_ROOT

_CHUNK = 1024 * 1024
_IGNORED_NAMES = frozenset({"README.md", "FIXTURE.md", ".gitkeep", ".DS_Store"})
PREVIEW_DIR = "preview"
"""The committed sample's human-readable preview; never ingested (its rows are copies of sample rows)."""


def file_md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


class LocalSource:
    """A local bucket layout; optionally list only contracted data files before hashing them."""

    def __init__(self, root: Path, *, kind: str = "local", known_tables_only: bool = False) -> None:
        if not root.is_dir():
            raise ConfigurationError(f"local source directory does not exist: {root}")
        self._root = root.resolve()
        self._kind = kind
        self._known_tables_only = known_tables_only

    @property
    def label(self) -> str:
        """The kind (``local`` or ``sample``) plus the path relative to the repository when it lies inside it."""
        try:
            shown = self._root.relative_to(REPOSITORY_ROOT).as_posix()
        except ValueError:
            shown = self._root.as_posix()
        return f"{self._kind}:{shown}"

    @property
    def prefix(self) -> str:
        return ""

    def list_objects(self) -> Iterator[SourceObject]:
        paths = sorted(self._data_paths() if self._known_tables_only else self._all_paths())
        for path in paths:
            stat = path.stat()
            yield SourceObject(
                key=path.relative_to(self._root).as_posix(),
                etag=file_md5(path),
                size=stat.st_size,
                last_modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            )

    def _all_paths(self) -> Iterator[Path]:
        for path in self._root.rglob("*"):
            if (
                path.is_file()
                and path.name not in _IGNORED_NAMES
                and not path.name.startswith(".")
                and path.relative_to(self._root).parts[0] != PREVIEW_DIR
            ):
                yield path

    def _data_paths(self) -> Iterator[Path]:
        """Visit only contracted roots, never EDA or warehouses inside the source tree."""
        for spec in TABLES:
            if spec.layout == "snapshot":
                candidates = (self._root / f"{spec.name}.{suffix}" for suffix in ("csv", "parquet"))
            else:
                table_dir = self._root / spec.name
                candidates = (
                    path for suffix in ("csv", "parquet") for path in table_dir.glob(f"year=*/month=*/day=*/*.{suffix}")
                )
            for path in candidates:
                if (
                    path.is_file()
                    and parse_key(path.relative_to(self._root).as_posix(), prefix="", snapshot_date=date.min)
                    is not None
                ):
                    yield path

    def download(self, obj: SourceObject, destination: Path) -> None:
        origin = self._root / obj.key
        if not origin.is_file():
            raise SourceAccessError(f"object disappeared from the local source: {obj.key}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_name(destination.name + ".partial")
        shutil.copyfile(origin, partial)
        partial.replace(destination)
