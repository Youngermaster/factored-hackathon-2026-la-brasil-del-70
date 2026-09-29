"""Typed pipeline errors. Each carries a stable code and the process exit code the CLI uses.

Messages are built from codes, keys, and counts only. They never include credentials, bucket names,
or the text of an underlying client exception, which may echo request details.
"""

from typing import ClassVar


class DataPlatformError(Exception):
    """Base class. ``code`` is stable and documented; ``exit_code`` is what ``bank-data`` returns."""

    code: ClassVar[str] = "data_platform_error"
    exit_code: ClassVar[int] = 1

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class ConfigurationError(DataPlatformError):
    code = "configuration_error"
    exit_code = 2


class SourceAccessError(DataPlatformError):
    """Listing or downloading from a data source failed after the allowed retries."""

    code = "source_access_error"
    exit_code = 4


class SourceMismatchError(DataPlatformError):
    """The warehouse manifest was built from a different source than the one requested."""

    code = "source_mismatch"
    exit_code = 2


class SchemaEvolutionError(DataPlatformError):
    """A batch removed a contract column or changed a column's type; the batch is quarantined."""

    code = "schema_breaking_change"
    exit_code = 3


class DbtError(DataPlatformError):
    code = "dbt_failed"
    exit_code = 5


class SampleError(DataPlatformError):
    """The committed sample could not meet its bounds or coverage."""

    code = "sample_error"
    exit_code = 6


class SeedVerificationError(DataPlatformError):
    """The PostgreSQL demo slice does not match the selected gold rows."""

    code = "seed_verification_failed"
