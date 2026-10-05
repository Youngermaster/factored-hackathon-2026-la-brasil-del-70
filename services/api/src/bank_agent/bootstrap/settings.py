"""Typed settings, organized per concern and read from the environment and, optionally, from secret files.

Environment variable names match the root ``.env.example`` exactly. Only this package reads the
environment. Secrets are ``SecretStr`` so they never appear in reprs, logs, or validation messages.

``SECRETS_DIR`` names a directory of mounted secret files, one file per variable named like the variable (for example
``/run/secrets/SESSION_SECRET``), as the production stack mounts them from Azure Key Vault (ADR 0037). Development and
tests leave it empty and keep using the environment and ``.env``. An environment variable still wins over a file, so in
production with ``SECRETS_DIR`` set, a secret variable in the environment is refused.

``load_settings`` enforces the production rules: ``DEMO_MODE`` must be false unless the public demo is allowed
explicitly, and every secret the process needs must be set, long enough, and not a known default. The API process and
the owner jobs (migrations, the seed, the retention purge) have separate rules, so the API never holds the owner
password. Violations raise ``SettingsError``, whose message names the offending variables and never their values.
"""

import ipaddress
import os
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from bank_agent.adapters.retrieval.embedding import DEFAULT_EMBEDDING_MODEL
from bank_agent.domain.conversation import MAX_CONVERSATION_CREATION_LIMIT, MAX_CONVERSATION_CREATION_WINDOW

Environment = Literal["development", "test", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LLMProvider = Literal["fake", "cassette", "litellm"]
LLMCassetteMode = Literal["replay", "record"]
BudgetLedgerName = Literal["auto", "memory", "postgres"]
RateLimitBackend = Literal["memory", "postgres"]

MIN_SECRET_LENGTH = 32
# A refused prefix, not a secret.
DEV_ONLY_SECRET_PREFIX = "dev-only-"  # noqa: S105  # nosec B105
"""Every development placeholder secret starts with this; production refuses any secret that does."""
DEV_ONLY_SECRETS: frozenset[str] = frozenset(
    {
        "dev-only-not-a-secret-postgres-owner-password",
        "dev-only-not-a-secret-postgres-app-password",
        "dev-only-not-a-secret-session-key-for-local-work-0000",
        "dev-only-not-a-secret-csrf-key-for-local-work-000000000",
    }
)
"""The placeholder secrets in ``.env.example``, so `cp .env.example .env` works in development only."""

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
    | DEV_ONLY_SECRETS
)

_ENV_FILE = Path(".env")
# settings.py -> bootstrap -> bank_agent -> src -> services/api -> services -> repository root
_SERVICE_ROOT = Path(__file__).resolve().parents[3]
_REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_PRICES_FILE = _SERVICE_ROOT / "config" / "llm_prices.yaml"
DEFAULT_CASSETTE_DIR = _REPOSITORY_ROOT / "evals" / "cassettes"
DEFAULT_POLICY_DIR = _REPOSITORY_ROOT / "policies"
DEFAULT_DATA_AS_OF = date(2026, 6, 17)
"""The organizer snapshot date (``data_platform/config/sources.yml``), the end of the seeded data."""
DEFAULT_INDEX_DIR = _REPOSITORY_ROOT / "data" / "artifacts" / "retrieval" / "indexes"
DEFAULT_EMBEDDING_CACHE_DIR = _REPOSITORY_ROOT / "data" / "artifacts" / "retrieval" / "embeddings"
DEFAULT_MODEL_CACHE_DIR = _REPOSITORY_ROOT / "data" / "models" / "huggingface"
DEFAULT_MODEL_REGISTRY_DIR = _REPOSITORY_ROOT / "data" / "artifacts" / "models"
DEFAULT_EVAL_SUMMARIES_DIR = _REPOSITORY_ROOT / "evals" / "reports" / "summaries"
_SELECTION = r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}"
ROUTER_SELECTION = rf"^(keyword@1|(tfidf|embeddings)@{_SELECTION})$"
RESOLVER_SELECTION = rf"^(rules@1|lgbm@{_SELECTION})$"
RISK_ESTIMATOR_SELECTION = rf"^(score_band@1|(logreg|lgbm)@{_SELECTION})$"
DEFAULT_THRESHOLD_BM25 = 3.6292
"""Tuned on the dev split of retrieval_judgments.v1 (docs/evaluation/retrieval.md); rerun `make eval-retrieval`."""
DEFAULT_THRESHOLD_DENSE = 0.8275
"""Cosine similarity with intfloat/multilingual-e5-small, tuned on the same dev split."""


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
    allow_public_demo_mode: bool = False
    """Production accepts ``DEMO_MODE=true`` only with this set (the public demo, docs/security/demo-mode.md)."""
    log_level: LogLevel = "INFO"
    secrets_dir: Path | None = None
    """A directory of mounted secret files named like their variables (``/run/secrets`` in the production stack)."""

    @field_validator("secrets_dir", mode="before")
    @classmethod
    def _empty_means_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


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
    """Session, CSRF, CORS, request size, and rate limit settings.

    Rate limits are requests per minute per rate class (``auth``, ``write``, ``read``), counted per client IP
    (``RATE_LIMIT_*_PER_MINUTE``) and per session (``RATE_LIMIT_SESSION_*_PER_MINUTE``). ``rate_limit_backend``
    chooses where the counters live: ``memory`` (one process, exact) or ``postgres`` (shared by every worker; required
    in production).
    """

    model_config = _config()

    session_secret: SecretStr | None = None
    csrf_secret: SecretStr | None = None
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:5173"])
    max_request_body_bytes: int = Field(default=16384, ge=1024, le=1_048_576)
    rate_limit_auth_per_minute: int = Field(default=10, ge=1, le=100_000)
    rate_limit_write_per_minute: int = Field(default=30, ge=1, le=100_000)
    rate_limit_read_per_minute: int = Field(default=120, ge=1, le=100_000)
    rate_limit_session_auth_per_minute: int = Field(default=10, ge=1, le=100_000)
    rate_limit_session_write_per_minute: int = Field(default=20, ge=1, le=100_000)
    rate_limit_session_read_per_minute: int = Field(default=60, ge=1, le=100_000)
    rate_limit_backend: RateLimitBackend = "memory"

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
    api_base: str = ""
    """Optional provider base URL passed to LiteLLM, for example ``http://localhost:11434`` for a local Ollama, or the
    Azure OpenAI resource endpoint ``https://<resource>.openai.azure.com/``."""
    api_version: str = Field(default="", pattern=r"^(\d{4}-\d{2}-\d{2}(-preview)?|v1|latest|preview)?$")
    """Optional Azure OpenAI data-plane API version passed to LiteLLM (``2024-10-21``, ``2025-04-01-preview``, or
    ``v1`` for the versionless API). Empty passes nothing, so LiteLLM uses its own default (``2025-02-01-preview`` in
    1.102.1)."""
    allow_private_http_base: bool = False
    """Production accepts a plain http ``api_base`` only with this set and a private host (a self-hosted model on the
    host's private network, such as the ``ollama`` compose profile); hosted providers always need https and a key."""
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
    budget_ledger: BudgetLedgerName = "auto"

    @field_validator("prices_file", "cassette_dir", mode="before")
    @classmethod
    def _empty_means_default(cls, value: object, info: ValidationInfo) -> object:
        if isinstance(value, str) and not value.strip():
            return DEFAULT_PRICES_FILE if info.field_name == "prices_file" else DEFAULT_CASSETTE_DIR
        return value


class PolicySettings(BaseSettings):
    """The synthetic policy pack and the reference date of policy time windows.

    ``data_as_of`` is the as-of date of the records (the organizer snapshot, 2026-06-17): dispute windows and
    complaint lookbacks count to it, never to the wall clock, because the data ends months before the demo.
    """

    model_config = _config("POLICY_")

    dir: Path = DEFAULT_POLICY_DIR
    data_as_of: date = DEFAULT_DATA_AS_OF

    @field_validator("dir", "data_as_of", mode="before")
    @classmethod
    def _empty_means_default(cls, value: object, info: ValidationInfo) -> object:
        if isinstance(value, str) and not value.strip():
            return DEFAULT_POLICY_DIR if info.field_name == "dir" else DEFAULT_DATA_AS_OF
        return value


RetrieverName = Literal["bm25", "dense", "hybrid"]
IndexSource = Literal["build", "stored"]


class RetrievalSettings(BaseSettings):
    """Open retrieval for informational questions (``docs/evaluation/retrieval.md`` justifies the defaults).

    ``index_source=build`` builds the BM25 index from the loaded pack at startup, so it matches by construction;
    ``stored`` loads ``<index_dir>/<pack version>/`` and refuses a mismatch; production requires ``stored``.
    ``dense`` and ``hybrid`` need the optional ``ml`` extra, which the API image never installs. The thresholds
    were tuned on the development split of the relevance judgments; the hybrid retriever uses them as the
    floors of its components.
    """

    model_config = _config("RETRIEVAL_")

    retriever: RetrieverName = "bm25"
    index_source: IndexSource = "build"
    index_dir: Path = DEFAULT_INDEX_DIR
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    model_cache_dir: Path = DEFAULT_MODEL_CACHE_DIR
    embedding_cache_dir: Path = DEFAULT_EMBEDDING_CACHE_DIR
    rrf_k: int = Field(default=60, ge=0, le=1000)
    threshold_bm25: float = Field(default=DEFAULT_THRESHOLD_BM25, ge=0)
    threshold_dense: float = Field(default=DEFAULT_THRESHOLD_DENSE, ge=-1, le=1)
    answer_k: int = Field(default=3, ge=1, le=20)

    @field_validator(
        "index_dir",
        "model_cache_dir",
        "embedding_cache_dir",
        "embedding_model",
        "threshold_bm25",
        "threshold_dense",
        mode="before",
    )
    @classmethod
    def _empty_means_default(cls, value: object, info: ValidationInfo) -> object:
        if isinstance(value, str) and not value.strip():
            return cls.model_fields[str(info.field_name)].default
        return value


class WorkflowSettings(BaseSettings):
    """The workflow engine: which workflows are enabled and whether the language model helps understanding.

    ``enabled`` lists the workflows the router may dispatch to (all four by default; for example
    ``WORKFLOW_ENABLED=dispute,card_support`` cuts the other two back);
    intents of any other workflow get the out-of-scope answer, which is also how a workflow is cut back
    (CLAUDE.md section 1). Model phrasing and handoff summaries are off by default and, when on, must pass the
    grounding verifier. Router, resolver, language detector, and risk estimator names select their implementations:
    ``WORKFLOW_ROUTER`` is ``keyword@1`` (default), ``tfidf@<version or alias>``, or ``embeddings@<version or alias>``;
    ``WORKFLOW_RESOLVER`` is ``rules@1`` (default) or ``lgbm@<version or alias>``; ``WORKFLOW_RISK_ESTIMATOR`` is
    ``score_band@1`` (default), ``logreg@<version or alias>``, or ``lgbm@<version or alias>``. Learned models load
    from the filesystem registry at ``WORKFLOW_MODEL_REGISTRY_DIR``; without an artifact the baseline serves.
    """

    model_config = _config("WORKFLOW_")

    enabled: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["account_inquiry", "card_support", "dispute", "credit"]
    )
    llm_understanding: bool = True
    llm_phrasing: bool = False
    llm_handoff_summary: bool = False
    max_turns: int = Field(default=40, ge=1, le=500)
    tool_timeout_seconds: float = Field(default=5.0, gt=0, le=120)
    router: Annotated[str, Field(pattern=ROUTER_SELECTION)] = "keyword@1"
    resolver: Annotated[str, Field(pattern=RESOLVER_SELECTION)] = "rules@1"
    model_registry_dir: Path = DEFAULT_MODEL_REGISTRY_DIR
    language_detector: Literal["lexical@1"] = "lexical@1"
    risk_estimator: Annotated[str, Field(pattern=RISK_ESTIMATOR_SELECTION)] = "score_band@1"
    max_eligibility_assessments: int = Field(default=5, ge=1, le=100)
    eligibility_assessment_window_minutes: int = Field(default=60, ge=1, le=1440)

    @field_validator("router", "resolver", "risk_estimator", "model_registry_dir", mode="before")
    @classmethod
    def _empty_model_means_default(cls, value: object, info: ValidationInfo) -> object:
        if isinstance(value, str) and not value.strip():
            return cls.model_fields[str(info.field_name)].default
        return value

    @field_validator("enabled", mode="before")
    @classmethod
    def _split_enabled(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


class EvaluationSettings(BaseSettings):
    """Published evaluation summaries served by ``/v1/eval/summaries``.

    ``summaries_dir`` holds the summary files the evaluation harness publishes (phase 14); a missing directory
    means nothing is published yet. ``summaries_public=true`` serves them without a session.
    """

    model_config = _config("EVAL_")

    summaries_dir: Path = DEFAULT_EVAL_SUMMARIES_DIR
    summaries_public: bool = False

    @field_validator("summaries_dir", mode="before")
    @classmethod
    def _empty_means_default(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return DEFAULT_EVAL_SUMMARIES_DIR
        return value


class ObservabilitySettings(BaseSettings):
    """OpenTelemetry settings (``docs/operations/observability.md``).

    Spans, trace ids, and the ``X-Trace-Id`` header always work; ``enabled`` only decides whether spans and metrics
    are exported over OTLP/HTTP to ``exporter_otlp_endpoint`` (the collector, which feeds Jaeger and Prometheus).
    ``traces_sampler_arg`` is the parent-based trace-id ratio (1.0 keeps every trace); ``metric_export_interval`` is
    in milliseconds, as in the OpenTelemetry specification.
    """

    model_config = _config("OTEL_")

    enabled: bool = False
    exporter_otlp_endpoint: str = "http://localhost:4318"
    service_name: str = "bank-agent-api"
    traces_sampler_arg: float = Field(default=1.0, ge=0.0, le=1.0)
    metric_export_interval: int = Field(default=15000, ge=1000, le=300_000)


class LangfuseSettings(BaseSettings):
    """Optional metadata-only export of LLM generation spans to Langfuse."""

    model_config = _config("LANGFUSE_")

    enabled: bool = False
    base_url: str = "http://localhost:3000"
    public_key: SecretStr | None = None
    secret_key: SecretStr | None = None


class DegradationSettings(BaseSettings):
    """One feature flag per fallback of the degradation ladder (``docs/operations/degradation.md``).

    - ``fallback_provider`` (L1): use ``LLM_FALLBACK_MODEL`` when the primary provider's circuit is open.
    - ``template_only`` (L2): while no provider can serve or the daily budget is spent, skip model calls entirely
      (off, each call still fails fast through the open circuit and falls back one by one).
    - ``model_baselines`` (L3): serve the keyword and rule baselines when a learned model cannot load; off, startup
      stops. ``router_threshold`` is the stricter keyword threshold used then.
    - ``risk_band_fallback`` (L3): a learned risk estimator that cannot load is replaced by ``score_band@1``; off
      (the default), every eligibility request goes to ``review_required``.
    - ``credit_catalog_fallback``: a credit catalog that cannot load disables the ``credit`` workflow; off, startup
      stops.
    - ``database_retry_after_seconds`` (L4): ``Retry-After`` on the 503. L4 has no flag: it always fails closed.
    """

    model_config = _config("DEGRADATION_")

    fallback_provider: bool = True
    template_only: bool = True
    model_baselines: bool = True
    router_threshold: float = Field(default=0.75, gt=0, le=1)
    risk_band_fallback: bool = False
    credit_catalog_fallback: bool = True
    database_retry_after_seconds: int = Field(default=30, ge=1, le=3600)


class RetentionSettings(BaseSettings):
    """Retention periods applied by ``bank-agent retention purge`` (``docs/security/data-retention.md``).

    - ``conversation_days``: conversation text (messages, turns, and their conversation) after the last activity.
    - ``session_days``: sessions, one-time-code challenges, and trust events after they end.
    - ``credit_application_days``: withdrawn or closed credit application intakes after their last status change;
      open intakes are kept until a person closes them.

    Execution records (no free text) and audit events are never purged by the job.
    """

    model_config = _config("RETENTION_")

    conversation_days: int = Field(default=7, ge=1, le=3650)
    session_days: int = Field(default=7, ge=1, le=3650)
    credit_application_days: int = Field(default=30, ge=1, le=3650)


DEFAULT_CONVERSATION_CREATION_LIMIT = 5
"""New chats per customer per window outside the public demo (ADR 0026)."""
PUBLIC_DEMO_CONVERSATION_CREATION_LIMIT = 200
"""The default with ``DEMO_MODE`` and ``ALLOW_PUBLIC_DEMO_MODE``, where every visitor shares a dozen seeded personas."""


class ConversationSettings(BaseSettings):
    """The customer quota on new chats (ADR 0026, ``docs/workflows/human-service.md``).

    A customer may create at most ``creation_limit`` new conversations in any rolling window of
    ``creation_window_minutes``, across sessions and workers; messages in existing chats never count. Left unset,
    the limit is 5, or 200 for the public demo (``DEMO_MODE`` and ``ALLOW_PUBLIC_DEMO_MODE`` both true), where every
    visitor signs in as one of the same seeded personas (``docs/security/demo-mode.md`` records the trade-off). An
    explicit value always wins.
    """

    model_config = _config("CONVERSATION_")

    creation_limit: int | None = Field(default=None, ge=1, le=MAX_CONVERSATION_CREATION_LIMIT)
    creation_window_minutes: int = Field(
        default=60, ge=1, le=int(MAX_CONVERSATION_CREATION_WINDOW.total_seconds() // 60)
    )

    @field_validator("creation_limit", "creation_window_minutes", mode="before")
    @classmethod
    def _empty_means_default(cls, value: object, info: ValidationInfo) -> object:
        if isinstance(value, str) and not value.strip():
            return cls.model_fields[str(info.field_name)].default
        return value

    def creation_limit_for(self, runtime: RuntimeSettings) -> int:
        """The explicit limit, else the public demo's default, else the standard default."""
        if self.creation_limit is not None:
            return self.creation_limit
        if runtime.demo_mode and runtime.allow_public_demo_mode:
            return PUBLIC_DEMO_CONVERSATION_CREATION_LIMIT
        return DEFAULT_CONVERSATION_CREATION_LIMIT


class AppSettings:
    """All settings for one process, validated together."""

    def __init__(
        self,
        runtime: RuntimeSettings,
        database: DatabaseSettings,
        security: SecuritySettings,
        llm: LLMSettings,
        observability: ObservabilitySettings,
        langfuse: LangfuseSettings | None = None,
        policy: PolicySettings | None = None,
        retrieval: RetrievalSettings | None = None,
        workflow: WorkflowSettings | None = None,
        evaluation: EvaluationSettings | None = None,
        degradation: DegradationSettings | None = None,
        retention: RetentionSettings | None = None,
        conversation: ConversationSettings | None = None,
    ) -> None:
        self.runtime = runtime
        self.database = database
        self.security = security
        self.llm = llm
        self.observability = observability
        self.langfuse = langfuse if langfuse is not None else LangfuseSettings(_env_file=None)
        self.policy = policy if policy is not None else PolicySettings()
        self.retrieval = retrieval if retrieval is not None else RetrievalSettings()
        self.workflow = workflow if workflow is not None else WorkflowSettings()
        self.evaluation = evaluation if evaluation is not None else EvaluationSettings()
        self.degradation = degradation if degradation is not None else DegradationSettings()
        self.retention = retention if retention is not None else RetentionSettings()
        self.conversation = conversation if conversation is not None else ConversationSettings()

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
    if value.lower().startswith(DEV_ONLY_SECRET_PREFIX):
        return f"{variable} must not be a development-only value in production"
    if value.lower() in KNOWN_DEFAULT_SECRETS:
        return f"{variable} must not be a known default value in production"
    if len(value) < MIN_SECRET_LENGTH:
        return f"{variable} must be at least {MIN_SECRET_LENGTH} characters in production"
    return None


def _origin_problems(origins: list[str]) -> list[str]:
    """Credentialed CORS needs an explicit allowlist of https origins in production."""
    if any(origin.strip() == "*" for origin in origins):
        return ["CORS_ALLOWED_ORIGINS must not contain * in production"]
    if any(not origin.startswith("https://") for origin in origins):
        return ["CORS_ALLOWED_ORIGINS must list https origins only in production"]
    return []


_PRIVATE_NETWORKS = tuple(
    ipaddress.ip_network(network)
    for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "::1/128", "fc00::/7")
)
"""RFC 1918 and unique local addresses plus loopback; documentation and other special ranges do not count."""


def _private_http_base(url: str) -> bool:
    """A plain http base whose host never leaves the machine's private network (a compose service or a private IP)."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "http" or not host:
        return False
    if host == "host.docker.internal" or "." not in host:
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(address in network for network in _PRIVATE_NETWORKS)


def _llm_problems(llm: LLMSettings) -> tuple[list[str], list[tuple[str, SecretStr | None]]]:
    """Model gateway rules: hosted providers need https and a key; a private-network model is the one exception."""
    problems: list[str] = []
    secrets: list[tuple[str, SecretStr | None]] = []
    private = llm.allow_private_http_base and _private_http_base(llm.api_base)
    if llm.provider == "litellm" and not private:
        secrets.append(("LLM_API_KEY_PRIMARY", llm.api_key_primary))
    if llm.api_base and not llm.api_base.startswith("https://") and not private:
        problems.append(
            "LLM_API_BASE must use https in production (plain http only with LLM_ALLOW_PRIVATE_HTTP_BASE=true "
            "and a private host)"
            if llm.allow_private_http_base
            else "LLM_API_BASE must use https in production"
        )
    if llm.trace_content:
        problems.append("LLM_TRACE_CONTENT must be false in production")
    if llm.provider == "cassette" and llm.cassette_mode == "record":
        problems.append("LLM_CASSETTE_MODE=record is not allowed in production")
    return problems, secrets


def production_problems(settings: AppSettings, *, owner: bool = False) -> list[str]:
    """Return every production rule the settings violate; empty outside production.

    ``owner=False`` checks the API process: it needs the application role, the session and CSRF secrets, and the
    HTTP rules, and must not receive the owner password. ``owner=True`` checks an owner job (migrations, the seed, the
    retention purge): it needs the owner password and ``SESSION_SECRET`` (the seed derives identity keys from it).
    """
    if not settings.is_production:
        return []
    problems: list[str] = []
    if owner:
        secrets: list[tuple[str, SecretStr | None]] = [
            ("SESSION_SECRET", settings.security.session_secret),
            ("POSTGRES_ADMIN_PASSWORD", settings.database.admin_password),
        ]
    else:
        if settings.runtime.demo_mode and not settings.runtime.allow_public_demo_mode:
            problems.append("DEMO_MODE must be false in production unless ALLOW_PUBLIC_DEMO_MODE=true")
        secrets = [
            ("SESSION_SECRET", settings.security.session_secret),
            ("CSRF_SECRET", settings.security.csrf_secret),
            ("POSTGRES_APP_PASSWORD", settings.database.app_password),
        ]
        if _is_set(settings.database.admin_password):
            problems.append("POSTGRES_ADMIN_PASSWORD must not be given to the API process in production")
        llm_problems, llm_secrets = _llm_problems(settings.llm)
        problems.extend(llm_problems)
        secrets.extend(llm_secrets)
        if settings.retrieval.index_source != "stored":
            problems.append(
                "RETRIEVAL_INDEX_SOURCE must be stored in production (build it with bank-agent index build)"
            )
        if settings.security.rate_limit_backend != "postgres":
            problems.append("RATE_LIMIT_BACKEND must be postgres in production, so every worker shares the limits")
        problems.extend(_origin_problems(settings.security.cors_allowed_origins))
        if settings.langfuse.enabled and not settings.langfuse.base_url.startswith("https://"):
            problems.append("LANGFUSE_BASE_URL must use https in production")
    for variable, secret in secrets:
        problem = _secret_problem(variable, secret)
        if problem is not None:
            problems.append(problem)
    return problems


def langfuse_problems(settings: AppSettings) -> list[str]:
    """Check opt-in export configuration without including secret values in diagnostics."""
    if not settings.langfuse.enabled:
        return []
    problems: list[str] = []
    if settings.llm.provider != "litellm":
        problems.append("LANGFUSE_ENABLED requires LLM_PROVIDER=litellm")
    if settings.llm.trace_content:
        problems.append("LLM_TRACE_CONTENT must be false when LANGFUSE_ENABLED=true")
    if settings.observability.enabled and settings.observability.exporter_otlp_endpoint.startswith(
        settings.langfuse.base_url.rstrip("/")
    ):
        problems.append("OTEL_EXPORTER_OTLP_ENDPOINT must not point to Langfuse when LANGFUSE_ENABLED=true")
    if not _is_set(settings.langfuse.public_key):
        problems.append("LANGFUSE_PUBLIC_KEY must be set when LANGFUSE_ENABLED=true")
    if not _is_set(settings.langfuse.secret_key):
        problems.append("LANGFUSE_SECRET_KEY must be set when LANGFUSE_ENABLED=true")
    try:
        target = urlsplit(settings.langfuse.base_url)
        valid_target = (
            target.scheme in {"http", "https"}
            and bool(target.hostname)
            and target.username is None
            and target.password is None
            and not target.query
            and not target.fragment
        )
    except ValueError:
        valid_target = False
    if not valid_target:
        problems.append("LANGFUSE_BASE_URL must be an HTTP URL without credentials, query, or fragment")
    return problems


SECRET_VARIABLES: tuple[str, ...] = (
    "POSTGRES_ADMIN_PASSWORD",
    "POSTGRES_APP_PASSWORD",
    "SESSION_SECRET",
    "CSRF_SECRET",
    "LLM_API_KEY_PRIMARY",
    "LLM_API_KEY_FALLBACK",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
)
"""Every variable that holds a secret; with ``SECRETS_DIR`` each one is a file of that name.

The production stack stages the first six (``deploy/secrets_stage.py``); it does not enable Langfuse, so its keys have
no staged file, but a file of that name is read and the environment is refused for them all the same.
"""


def secret_source_problems(settings: AppSettings, environ: Mapping[str, str]) -> list[str]:
    """In production with ``SECRETS_DIR``, secrets come only from its files, never from the environment.

    An environment variable outranks a secret file, so a leftover variable would silently replace the Key Vault value
    and would show in ``docker inspect`` and in the rendered compose configuration (ADR 0037).
    """
    if not settings.is_production or settings.runtime.secrets_dir is None:
        return []
    return [
        f"{name} must come from SECRETS_DIR, not from the environment, in production"
        for name in SECRET_VARIABLES
        if environ.get(name, "").strip()
    ]


def load_settings(
    env_file: Path | None = _ENV_FILE, *, owner: bool = False, environ: Mapping[str, str] | None = None
) -> AppSettings:
    """Load and validate settings from the environment, the env file when present, and ``SECRETS_DIR`` when set.

    Pass ``env_file=None`` to read the process environment only, as tests do. ``owner=True`` validates the settings
    of an owner job (migrations, the seed, the retention purge) instead of the API's. ``environ`` is the environment
    checked by the secret source rule; it defaults to the process environment.
    """
    runtime = RuntimeSettings(_env_file=env_file)
    secrets_dir = runtime.secrets_dir
    if secrets_dir is not None and not secrets_dir.is_dir():
        raise SettingsError(["SECRETS_DIR must name an existing directory of secret files"])
    settings = AppSettings(
        runtime=runtime,
        database=DatabaseSettings(_env_file=env_file, _secrets_dir=secrets_dir),
        security=SecuritySettings(_env_file=env_file, _secrets_dir=secrets_dir),
        llm=LLMSettings(_env_file=env_file, _secrets_dir=secrets_dir),
        observability=ObservabilitySettings(_env_file=env_file),
        langfuse=LangfuseSettings(_env_file=env_file, _secrets_dir=secrets_dir),
        policy=PolicySettings(_env_file=env_file),
        retrieval=RetrievalSettings(_env_file=env_file),
        workflow=WorkflowSettings(_env_file=env_file),
        evaluation=EvaluationSettings(_env_file=env_file),
        degradation=DegradationSettings(_env_file=env_file),
        retention=RetentionSettings(_env_file=env_file),
        conversation=ConversationSettings(_env_file=env_file),
    )
    problems = production_problems(settings, owner=owner)
    problems.extend(secret_source_problems(settings, os.environ if environ is None else environ))
    if not owner:
        problems.extend(langfuse_problems(settings))
    if problems:
        raise SettingsError(problems)
    return settings
