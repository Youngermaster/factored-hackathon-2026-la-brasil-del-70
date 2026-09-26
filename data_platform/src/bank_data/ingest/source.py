"""The ``DataSource`` port: where organizer objects come from.

This is the repository pattern for data origins. The ingestion runner only lists and downloads through
this Protocol, so adding an origin (another bucket, an HTTP export, a database dump) means one new adapter.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class SourceObject:
    key: str
    """The full object key, including the source prefix."""
    etag: str
    """A content fingerprint: the S3 ETag, or the MD5 of a local file (the same value S3 uses for
    single-part uploads)."""
    size: int
    last_modified: datetime
    """Timezone-aware."""


class DataSource(Protocol):
    """Lists and downloads raw objects.

    Preconditions: none; construction validates configuration.
    Postconditions: ``list_objects`` yields every object under the prefix exactly once, in key order.
    ``download`` writes the complete object to ``destination`` atomically (a partial file never remains).
    Errors: ``SourceAccessError`` after the allowed retries; messages never contain credentials.
    Isolation: read only; a source never writes to its origin.
    """

    @property
    def label(self) -> str:
        """A non-secret description of the origin, recorded in the manifest (``s3`` or ``local:<dir>``)."""
        ...

    @property
    def prefix(self) -> str:
        """The key prefix that precedes table names (``data/`` for the organizer bucket)."""
        ...

    def list_objects(self) -> Iterator[SourceObject]:
        """Yield every object under the prefix."""
        ...

    def download(self, obj: SourceObject, destination: Path) -> None:
        """Write the object's bytes to ``destination``."""
        ...
