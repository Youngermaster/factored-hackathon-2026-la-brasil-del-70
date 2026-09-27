"""``S3Source``: the organizer bucket through boto3.

Listing uses the paginator; downloads stream the body to a partial file in chunks and rename it only after
the byte count matches, so an interrupted download never leaves a truncated object. Transient failures
(throttling, 5xx, connection and read errors) are retried with bounded exponential backoff on top of the
botocore standard retry mode. Errors surface as ``SourceAccessError`` built from the error code and the key
only: the bucket name, credentials, and the client's own message (which may echo request details) never
reach a log or an exception.
"""

import time
from collections.abc import Callable, Iterator
from datetime import UTC
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, ConnectionError, ReadTimeoutError
from urllib3.exceptions import ProtocolError

from bank_data.errors import ConfigurationError, SourceAccessError
from bank_data.ingest.source import SourceObject
from bank_data.settings import S3Settings

_CHUNK = 8 * 1024 * 1024
_TRANSIENT_CODES = frozenset(
    {
        "InternalError",
        "ServiceUnavailable",
        "SlowDown",
        "Throttling",
        "ThrottlingException",
        "RequestTimeout",
        "RequestTimeoutException",
        "500",
        "502",
        "503",
        "504",
    }
)


def error_code(error: BaseException) -> str:
    """A non-secret code for ``error``: the S3 error code, or the exception class name."""
    if isinstance(error, ClientError):
        code = error.response.get("Error", {}).get("Code")
        return str(code) if code else "ClientError"
    return type(error).__name__


def is_transient(error: BaseException) -> bool:
    if isinstance(error, ClientError):
        return error_code(error) in _TRANSIENT_CODES
    return isinstance(error, ConnectionError | ReadTimeoutError | ProtocolError | OSError)


class S3Source:
    def __init__(
        self,
        client: Any,
        bucket: str,
        prefix: str,
        *,
        attempts: int = 4,
        backoff_seconds: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if attempts < 1:
            raise ConfigurationError("attempts must be at least 1")
        self._client = client
        self._bucket = bucket
        self._prefix = prefix
        self._attempts = attempts
        self._backoff = backoff_seconds
        self._sleep = sleep

    @classmethod
    def from_settings(cls, settings: S3Settings) -> "S3Source":
        if settings.data_bucket is None:
            raise ConfigurationError("DATA_BUCKET is not set")
        session = boto3.session.Session(
            aws_access_key_id=(settings.aws_access_key_id.get_secret_value() if settings.aws_access_key_id else None),
            aws_secret_access_key=(
                settings.aws_secret_access_key.get_secret_value() if settings.aws_secret_access_key else None
            ),
            region_name=settings.aws_default_region,
        )
        config = Config(retries={"max_attempts": 5, "mode": "standard"}, connect_timeout=10, read_timeout=60)
        return cls(session.client("s3", config=config), settings.data_bucket, settings.data_prefix)

    @property
    def label(self) -> str:
        return "s3"

    @property
    def prefix(self) -> str:
        return self._prefix

    def _with_retries[T](self, action: Callable[[], T], describe: str) -> T:
        last: BaseException | None = None
        for attempt in range(1, self._attempts + 1):
            try:
                return action()
            except (ClientError, BotoCoreError, ProtocolError, OSError) as error:
                last = error
                if not is_transient(error) or attempt == self._attempts:
                    break
                self._sleep(self._backoff * 2 ** (attempt - 1))
        code = error_code(last) if last is not None else "unknown"
        raise SourceAccessError(f"{describe} failed ({code})") from None

    def list_objects(self) -> Iterator[SourceObject]:
        def collect() -> list[SourceObject]:
            found: list[SourceObject] = []
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self._bucket, Prefix=self._prefix):
                for item in page.get("Contents", []):
                    key = item["Key"]
                    if key.endswith("/"):
                        continue
                    modified = item["LastModified"]
                    found.append(
                        SourceObject(
                            key=key,
                            etag=str(item["ETag"]).strip('"'),
                            size=int(item["Size"]),
                            last_modified=modified if modified.tzinfo else modified.replace(tzinfo=UTC),
                        )
                    )
            return sorted(found, key=lambda obj: obj.key)

        yield from self._with_retries(collect, "listing the bucket prefix")

    def download(self, obj: SourceObject, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_name(destination.name + ".partial")

        def fetch() -> None:
            response = self._client.get_object(Bucket=self._bucket, Key=obj.key)
            written = 0
            with partial.open("wb") as handle:
                for chunk in response["Body"].iter_chunks(_CHUNK):
                    handle.write(chunk)
                    written += len(chunk)
            if written != obj.size:
                partial.unlink(missing_ok=True)
                raise OSError(f"size mismatch for {obj.key}: expected {obj.size}, received {written}")
            partial.replace(destination)

        try:
            self._with_retries(fetch, f"downloading {obj.key}")
        finally:
            partial.unlink(missing_ok=True)
