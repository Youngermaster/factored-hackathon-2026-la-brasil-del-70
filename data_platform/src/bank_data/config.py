"""The source configuration file (``data_platform/config/sources.yml``), parsed into typed values."""

from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from bank_data.errors import ConfigurationError


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Freshness(_Frozen):
    warn_after_hours: int = Field(ge=1)
    error_after_hours: int = Field(ge=1)


class DatasetConfig(_Frozen):
    version: str
    snapshot_date: date


class IngestConfig(_Frozen):
    type_change_threshold: float = Field(gt=0, le=1)


class BuildConfig(_Frozen):
    lookback_days: int = Field(ge=0, le=365)


class FreshnessConfig(_Frozen):
    default: Freshness
    tables: dict[str, Freshness] = Field(default_factory=dict)

    def for_table(self, table: str) -> Freshness:
        return self.tables.get(table, self.default)


class SourceConfig(_Frozen):
    dataset: DatasetConfig
    ingest: IngestConfig
    build: BuildConfig
    freshness: FreshnessConfig


def load_config(path: Path) -> SourceConfig:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ConfigurationError(f"cannot read the source configuration {path.name}: {type(error).__name__}") from None
    try:
        return SourceConfig.model_validate(document)
    except ValueError as error:
        raise ConfigurationError(f"invalid source configuration {path.name}: {error}") from None
