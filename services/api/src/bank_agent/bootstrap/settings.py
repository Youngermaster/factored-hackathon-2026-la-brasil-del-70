"""Typed settings, organized per concern and read only from the environment.

Environment variable names match the root ``.env.example`` exactly. Only this package reads the
environment. Secrets are ``SecretStr`` so they never appear in reprs, logs, or validation messages.

``load_settings`` enforces the production rules: ``DEMO_MODE`` must be false, and every secret must be
set, long enough, and not a known default. Violations raise ``SettingsError``, whose message names the
offending variables and never their values.
"""

from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Environment = Literal["development", "test", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LLMProvider = Literal["fake", "cassette", "litellm"]
LLMCassetteMode = Literal["replay", "record"]

MIN_SECRET_LENGTH = 32

# Values that must never be accepted as a production secret, compared case-insensitively.
KNOWN_DEFAULT_SECRETS: frozenset[str] = frozenset(
    {
        "admin",
        "change-me",
        "changeme",
        "changeit",
        "default",
        "dev",
        "development",
        "example",
        "insecure",
        "letmein",
        "password",
        "postgres",
        "secret",
        "test",
    }
)

_ENV_FILE = Path(".env")
# settings.py -> bootstrap -> bank_agent -> src -> services/api -> services -> repository root
_SERVICE_ROOT = Path(__file__).resolve().parents[3]
_REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_PRICES_FILE = _SERVICE_ROOT / "config" / "llm_prices.yaml"
DEFAULT_CASSETTE_DIR = _REPOSITORY_ROOT / "evals" / "cassettes"


def _config(prefix: str = "") -> SettingsConfigDict:
    return SettingsConfigDict(
        env_prefix=prefix,
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


class RuntimeSettings(BaseSettings):
    """Deployment environment and runtime switches."""

    model_config = _config()

    app_env: Environment = "development"
    demo_mode: bool = False
    log_level: LogLevel = "INFO"


class DatabaseSettings(BaseSettings):
    """PostgreSQL connection settings for the owner (migrations) and application roles."""

    model_config = _config("POSTGRES_")

    host: str = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)
    db: str = "bank_agent"
    admin_user: str = "bank_owner"
    admin_password: SecretStr | None = None
    app_user: str = "bank_app"
    app_password: SecretStr | None = None

    @property
    def is_configured(self) -> bool:
        """The API connects as the application role, so it is configured once that password is set."""
        return _is_set(self.app_password)


class SecuritySettings(BaseSettings):
    """Session, CSRF, and CORS settings."""

    model_config = _config()

    session_secret: SecretStr | None = None
    csrf_secret: SecretStr | None = None
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:5173"])

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


class LLMSettings(BaseSettings):
    """Language model gateway settings. Provider and model are chosen by evaluation.

    ``provider``: ``fake`` uses a client injected by tests or the evaluation harness, or, when none is injected,
    a client that refuses every call so workflows take their deterministic fallbacks; ``cassette`` replays (or
    records) cassettes; ``litellm`` calls a live provider through the optional ``litellm`` extra.
    """

    model_config = _config("LLM_")

    provider: LLMProvider = "fake"
    primary_model: str = ""
    fallback_model: str = ""
    api_key_primary: SecretStr | None = None
    api_key_fallback: SecretStr | None = None
    daily_budget_usd: Decimal = Field(default=Decimal(5), ge=0)
    session_token_limit: int = Field(default=20000, gt=0)
    conversation_budget_usd: Decimal = Field(default=Decimal("0.50"), ge=0)
    timeout_seconds: float = Field(default=20.0, gt=0, le=300)
    max_retries: int = Field(default=2, ge=0, le=2)
    retry_base_delay_seconds: float = Field(default=0.5, ge=0, le=30)
    retry_max_delay_seconds: float = Field(default=4.0, ge=0, le=60)
    circuit_failure_threshold: int = Field(default=5, ge=1, le=100)
    circuit_reset_seconds: float = Field(default=30.0, gt=0, le=3600)
    circuit_half_open_max_calls: int = Field(default=1, ge=1, le=10)
    prices_file: Path = DEFAULT_PRICES_FILE
    cassette_mode: LLMCassetteMode = "replay"
    cassette_dir: Path = DEFAULT_CASSETTE_DIR
    trace_content: bool = False

    @field_validator("prices_file", "cassette_dir", mode="before")
    @classmethod
    def _empty_means_default(cls, value: object, info: ValidationInfo) -> object:
        if isinstance(value, str) and not value.strip():
            return DEFAULT_PRICES_FILE if info.field_name == "prices_file" else DEFAULT_CASSETTE_DIR
        return value


class ObservabilitySettings(BaseSettings):
    """OpenTelemetry export settings."""

    model_config = _config("OTEL_")

    exporter_otlp_endpoint: str = "http://localhost:4317"
    service_name: str = "bank-agent-api"


class AppSettings:
    """All settings for one process, validated together."""

    def __init__(
        self,
        runtime: RuntimeSettings,
        database: DatabaseSettings,
        security: SecuritySettings,
        llm: LLMSettings,
        observability: ObservabilitySettings,
    ) -> None:
        self.runtime = runtime
        self.database = database
        self.security = security
        self.llm = llm
        self.observability = observability

    @property
    def is_production(self) -> bool:
        return self.runtime.app_env == "production"


class SettingsError(ValueError):
    """Raised when settings are unsafe for the selected environment. Never carries secret values."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("unsafe settings: " + "; ".join(problems))


def _is_set(secret: SecretStr | None) -> bool:
    return secret is not None and bool(secret.get_secret_value().strip())


def _secret_problem(variable: str, secret: SecretStr | None) -> str | None:
    """Describe why a production secret is unacceptable, without revealing it."""
    value = secret.get_secret_value().strip() if secret is not None else ""
    if not value:
        return f"{variable} must be set in production"
    if value.lower() in KNOWN_DEFAULT_SECRETS:
        return f"{variable} must not be a known default value in production"
    if len(value) < MIN_SECRET_LENGTH:
        return f"{variable} must be at least {MIN_SECRET_LENGTH} characters in production"
    return None


def production_problems(settings: AppSettings) -> list[str]:
    """Return every production rule the settings violate; empty outside production."""
    if not settings.is_production:
        return []
    problems: list[str] = []
    if settings.runtime.demo_mode:
        problems.append("DEMO_MODE must be false in production")
    secrets: list[tuple[str, SecretStr | None]] = [
        ("SESSION_SECRET", settings.security.session_secret),
        ("CSRF_SECRET", settings.security.csrf_secret),
        ("POSTGRES_ADMIN_PASSWORD", settings.database.admin_password),
        ("POSTGRES_APP_PASSWORD", settings.database.app_password),
    ]
    if settings.llm.provider == "litellm":
        secrets.append(("LLM_API_KEY_PRIMARY", settings.llm.api_key_primary))
    if settings.llm.trace_content:
        problems.append("LLM_TRACE_CONTENT must be false in production")
    if settings.llm.provider == "cassette" and settings.llm.cassette_mode == "record":
        problems.append("LLM_CASSETTE_MODE=record is not allowed in production")
    for variable, secret in secrets:
        problem = _secret_problem(variable, secret)
        if problem is not None:
            problems.append(problem)
    return problems


def load_settings(env_file: Path | None = _ENV_FILE) -> AppSettings:
    """Load and validate settings from the environment and, when present, the env file.

    Pass ``env_file=None`` to read the process environment only, as tests do.
    """
    settings = AppSettings(
        runtime=RuntimeSettings(_env_file=env_file),
        database=DatabaseSettings(_env_file=env_file),
        security=SecuritySettings(_env_file=env_file),
        llm=LLMSettings(_env_file=env_file),
        observability=ObservabilitySettings(_env_file=env_file),
    )
    problems = production_problems(settings)
    if problems:
        raise SettingsError(problems)
    return settings
