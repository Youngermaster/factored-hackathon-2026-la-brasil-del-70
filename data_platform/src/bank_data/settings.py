"""Typed settings for the data platform, read only from the environment (and the local ``.env`` file).

The S3 credentials are ``SecretStr``: they never appear in reprs, logs, validation messages, or the
environment handed to dbt. Names match the root ``.env.example``.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SourceKind = Literal["sample", "s3", "local"]
"""``sample``: the committed ``data_platform/sample/``; ``s3``: the organizer bucket; ``local``: any directory."""

# settings.py -> bank_data -> src -> data_platform -> repository root
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DATA_PLATFORM_ROOT = REPOSITORY_ROOT / "data_platform"
DEFAULT_SAMPLE_DIR = DATA_PLATFORM_ROOT / "sample"
DEFAULT_CONFIG_FILE = DATA_PLATFORM_ROOT / "config" / "sources.yml"
DBT_PROJECT_DIR = DATA_PLATFORM_ROOT / "dbt"


def _config() -> SettingsConfigDict:
    return SettingsConfigDict(
        env_file=Path(".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


def _blank_to_none(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        return None
    return value


class S3Settings(BaseSettings):
    """Organizer bucket access. Every value is optional so offline work needs none of them."""

    model_config = _config()

    aws_access_key_id: SecretStr | None = None
    aws_secret_access_key: SecretStr | None = None
    aws_default_region: str | None = None
    data_bucket: str | None = Field(default=None, repr=False)
    data_prefix: str = "data/"

    _normalize = field_validator(
        "aws_access_key_id", "aws_secret_access_key", "aws_default_region", "data_bucket", mode="before"
    )(_blank_to_none)

    @property
    def configured(self) -> bool:
        """True when a bucket is named; credentials may still come from the default boto3 chain."""
        return self.data_bucket is not None

    def secret_values(self) -> tuple[str, ...]:
        """The values that must never appear in output (used by redaction and tests)."""
        values = [self.data_bucket or ""]
        for secret in (self.aws_access_key_id, self.aws_secret_access_key):
            if secret is not None:
                values.append(secret.get_secret_value())
        return tuple(value for value in values if value)


class PipelineSettings(BaseSettings):
    """Where the pipeline keeps its files and how DuckDB may use the machine."""

    model_config = _config()

    bank_data_source: Literal["sample", "s3"] = "sample"
    """The explicit data source. ``sample`` needs no network or credentials; ``s3`` reads the organizer bucket."""
    bank_data_dir: Path = REPOSITORY_ROOT / "data"
    bank_data_warehouse_dir: Path | None = None
    """Overrides the per-source default: ``warehouse`` (s3), ``warehouse-sample`` (sample), ``warehouse-local``."""
    bank_data_config_file: Path = DEFAULT_CONFIG_FILE
    bank_data_duckdb_memory_limit: str = "8GB"
    bank_data_duckdb_threads: int = Field(default=8, ge=1, le=128)
    bank_data_ingest_workers: int = Field(default=6, ge=1, le=64)

    _normalize = field_validator("bank_data_warehouse_dir", mode="before")(_blank_to_none)

    def warehouse_dir(self, source: SourceKind) -> Path:
        if self.bank_data_warehouse_dir is not None:
            return self.bank_data_warehouse_dir
        names = {"s3": "warehouse", "sample": "warehouse-sample", "local": "warehouse-local"}
        return self.bank_data_dir / names[source]
