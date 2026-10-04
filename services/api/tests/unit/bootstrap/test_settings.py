import secrets
from decimal import Decimal
from pathlib import Path

import pytest

from bank_agent.bootstrap.settings import MIN_SECRET_LENGTH, SettingsError, load_settings

SECRET_VARIABLES = ("SESSION_SECRET", "CSRF_SECRET", "POSTGRES_APP_PASSWORD")
"""The secrets the API process needs in production (the owner password never reaches it)."""


def _strong_secret() -> str:
    return secrets.token_urlsafe(48)


@pytest.fixture
def production_environment(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """A complete, valid production environment with secrets generated for this test."""
    values = {
        "APP_ENV": "production",
        "DEMO_MODE": "false",
        "RETRIEVAL_INDEX_SOURCE": "stored",
        "CORS_ALLOWED_ORIGINS": "https://bank.example",
        "RATE_LIMIT_BACKEND": "postgres",
    }
    values.update({name: _strong_secret() for name in SECRET_VARIABLES})
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    return values


def test_development_defaults_load_without_environment_or_env_file() -> None:
    settings = load_settings(env_file=None)

    assert settings.runtime.app_env == "development"
    assert settings.runtime.demo_mode is False
    assert settings.database.is_configured is False
    assert settings.llm.provider == "fake"
    assert settings.llm.daily_budget_usd == Decimal(5)
    assert settings.security.cors_allowed_origins == ["http://localhost:5173"]


def test_development_allows_demo_mode_and_empty_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")

    settings = load_settings(env_file=None)

    assert settings.runtime.demo_mode is True
    assert settings.security.session_secret is None


def test_production_accepts_a_complete_valid_environment(production_environment: dict[str, str]) -> None:
    settings = load_settings(env_file=None)

    assert settings.is_production
    assert settings.database.is_configured


def test_production_refuses_demo_mode(production_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")

    with pytest.raises(SettingsError) as raised:
        load_settings(env_file=None)

    assert raised.value.problems == ["DEMO_MODE must be false in production unless ALLOW_PUBLIC_DEMO_MODE=true"]


def test_production_accepts_demo_mode_only_when_the_public_demo_is_allowed(
    production_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("ALLOW_PUBLIC_DEMO_MODE", "true")

    settings = load_settings(env_file=None)

    assert settings.runtime.demo_mode is True
    assert settings.runtime.allow_public_demo_mode is True


def test_the_public_demo_flag_alone_does_not_turn_demo_mode_on(
    production_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALLOW_PUBLIC_DEMO_MODE", "true")

    assert load_settings(env_file=None).runtime.demo_mode is False


@pytest.mark.parametrize("variable", SECRET_VARIABLES)
def test_production_refuses_a_missing_secret(
    production_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    monkeypatch.delenv(variable)

    with pytest.raises(SettingsError) as raised:
        load_settings(env_file=None)

    assert raised.value.problems == [f"{variable} must be set in production"]


@pytest.mark.parametrize("variable", SECRET_VARIABLES)
def test_production_refuses_a_blank_secret(
    production_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    monkeypatch.setenv(variable, "   ")

    with pytest.raises(SettingsError) as raised:
        load_settings(env_file=None)

    assert raised.value.problems == [f"{variable} must be set in production"]


@pytest.mark.parametrize("variable", SECRET_VARIABLES)
def test_production_refuses_a_short_secret(
    production_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    monkeypatch.setenv(variable, "x" * (MIN_SECRET_LENGTH - 1))

    with pytest.raises(SettingsError) as raised:
        load_settings(env_file=None)

    assert raised.value.problems == [f"{variable} must be at least {MIN_SECRET_LENGTH} characters in production"]


@pytest.mark.parametrize("variable", SECRET_VARIABLES)
@pytest.mark.parametrize("default_value", ["changeme", "PASSWORD", "secret"])
def test_production_refuses_a_known_default_secret(
    production_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch, variable: str, default_value: str
) -> None:
    monkeypatch.setenv(variable, default_value)

    with pytest.raises(SettingsError) as raised:
        load_settings(env_file=None)

    assert raised.value.problems == [f"{variable} must not be a known default value in production"]


def test_production_reports_every_problem_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_MODE", "true")

    with pytest.raises(SettingsError) as raised:
        load_settings(env_file=None)

    assert len(raised.value.problems) == 4 + len(SECRET_VARIABLES)
    assert any(problem.startswith("RETRIEVAL_INDEX_SOURCE must be stored") for problem in raised.value.problems)


def test_retrieval_defaults_and_production_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load_settings(env_file=None)
    assert settings.retrieval.retriever == "bm25"
    assert settings.retrieval.index_source == "build"
    assert settings.retrieval.embedding_model == "intfloat/multilingual-e5-small"
    assert settings.retrieval.index_dir.is_absolute()
    monkeypatch.setenv("RETRIEVAL_INDEX_DIR", "")
    monkeypatch.setenv("RETRIEVAL_THRESHOLD_BM25", "")
    monkeypatch.setenv("RETRIEVAL_RETRIEVER", "hybrid")
    reloaded = load_settings(env_file=None)
    assert reloaded.retrieval.index_dir == settings.retrieval.index_dir
    assert reloaded.retrieval.retriever == "hybrid"
    assert reloaded.retrieval.threshold_bm25 == settings.retrieval.threshold_bm25


def test_settings_error_never_contains_the_secret_value(
    production_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    rejected_value = "short-" + secrets.token_hex(4)
    monkeypatch.setenv("SESSION_SECRET", rejected_value)

    with pytest.raises(SettingsError) as raised:
        load_settings(env_file=None)

    assert "SESSION_SECRET" in str(raised.value)
    assert rejected_value not in str(raised.value)
    assert rejected_value not in repr(raised.value)


def test_secret_values_are_hidden_in_settings_reprs(production_environment: dict[str, str]) -> None:
    settings = load_settings(env_file=None)

    rendered = repr(settings.security) + repr(settings.database)

    assert production_environment["SESSION_SECRET"] not in rendered
    assert production_environment["POSTGRES_APP_PASSWORD"] not in rendered


def test_production_with_litellm_requires_the_primary_key(
    production_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "litellm")

    with pytest.raises(SettingsError) as raised:
        load_settings(env_file=None)

    assert raised.value.problems == ["LLM_API_KEY_PRIMARY must be set in production"]


def test_production_with_litellm_accepts_a_strong_primary_key(
    production_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "litellm")
    monkeypatch.setenv("LLM_API_KEY_PRIMARY", _strong_secret())

    assert load_settings(env_file=None).llm.provider == "litellm"


def test_production_langfuse_export_requires_https(
    production_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "litellm")
    monkeypatch.setenv("LLM_API_KEY_PRIMARY", _strong_secret())
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "fixture-public-key")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", _strong_secret())
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://langfuse.example")

    with pytest.raises(SettingsError) as raised:
        load_settings(env_file=None)

    assert raised.value.problems == ["LANGFUSE_BASE_URL must use https in production"]
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://langfuse.example")
    assert load_settings(env_file=None).langfuse.enabled


def test_cors_origins_parse_from_a_comma_separated_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173, https://demo.example.org ,")

    settings = load_settings(env_file=None)

    assert settings.security.cors_allowed_origins == ["http://localhost:5173", "https://demo.example.org"]


def test_values_are_read_from_the_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / "settings.env"
    env_file.write_text("LOG_LEVEL=DEBUG\nPOSTGRES_PORT=6543\nOTEL_SERVICE_NAME=bank-agent-test\n", encoding="utf-8")

    settings = load_settings(env_file=env_file)

    assert settings.runtime.log_level == "DEBUG"
    assert settings.database.port == 6543
    assert settings.observability.service_name == "bank-agent-test"


def test_example_env_file_can_be_copied_and_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    example = Path(__file__).resolve().parents[5] / ".env.example"

    settings = load_settings(env_file=example)

    assert settings.retrieval.threshold_bm25 is not None
    assert settings.database.port == 5432


def test_database_is_configured_once_the_application_password_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_APP_PASSWORD", _strong_secret())

    assert load_settings(env_file=None).database.is_configured


@pytest.mark.parametrize(
    ("origins", "problem"),
    [
        ("*", "CORS_ALLOWED_ORIGINS must not contain * in production"),
        (
            "https://bank.example,http://localhost:5173",
            "CORS_ALLOWED_ORIGINS must list https origins only in production",
        ),
    ],
)
def test_production_refuses_wildcard_and_plain_http_origins(
    production_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch, origins: str, problem: str
) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", origins)

    with pytest.raises(SettingsError) as raised:
        load_settings(env_file=None)

    assert raised.value.problems == [problem]


def test_production_refuses_a_plain_http_llm_base_url(
    production_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_API_BASE", "http://localhost:11434")

    with pytest.raises(SettingsError) as raised:
        load_settings(env_file=None)

    assert raised.value.problems == ["LLM_API_BASE must use https in production"]


def test_security_limits_and_evaluation_settings_have_documented_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load_settings(env_file=None)
    assert settings.security.max_request_body_bytes == 16384
    assert settings.security.rate_limit_auth_per_minute == 10
    assert settings.security.rate_limit_session_write_per_minute == 20
    assert settings.evaluation.summaries_public is False
    assert settings.evaluation.summaries_dir.is_absolute()
    monkeypatch.setenv("EVAL_SUMMARIES_DIR", "")
    monkeypatch.setenv("EVAL_SUMMARIES_PUBLIC", "true")
    reloaded = load_settings(env_file=None)
    assert reloaded.evaluation.summaries_dir == settings.evaluation.summaries_dir
    assert reloaded.evaluation.summaries_public is True


def test_production_refuses_the_owner_password_in_the_api_process(
    production_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POSTGRES_ADMIN_PASSWORD", _strong_secret())

    with pytest.raises(SettingsError) as raised:
        load_settings(env_file=None)

    assert raised.value.problems == ["POSTGRES_ADMIN_PASSWORD must not be given to the API process in production"]


def test_production_refuses_a_per_process_rate_limiter(
    production_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")

    with pytest.raises(SettingsError) as raised:
        load_settings(env_file=None)

    assert raised.value.problems == [
        "RATE_LIMIT_BACKEND must be postgres in production, so every worker shares the limits"
    ]


@pytest.fixture
def owner_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """What an owner job receives in production: the owner password and the session secret only."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("POSTGRES_ADMIN_PASSWORD", _strong_secret())
    monkeypatch.setenv("SESSION_SECRET", _strong_secret())


@pytest.mark.usefixtures("owner_environment")
def test_owner_jobs_need_only_the_owner_password_and_the_session_secret() -> None:
    settings = load_settings(env_file=None, owner=True)

    assert settings.is_production
    assert settings.database.admin_password is not None
    assert settings.database.app_password is None


@pytest.mark.usefixtures("owner_environment")
@pytest.mark.parametrize("variable", ["POSTGRES_ADMIN_PASSWORD", "SESSION_SECRET"])
def test_owner_jobs_refuse_a_missing_or_weak_secret(monkeypatch: pytest.MonkeyPatch, variable: str) -> None:
    monkeypatch.delenv(variable)
    with pytest.raises(SettingsError) as missing:
        load_settings(env_file=None, owner=True)
    monkeypatch.setenv(variable, "changeme")
    with pytest.raises(SettingsError) as weak:
        load_settings(env_file=None, owner=True)

    assert missing.value.problems == [f"{variable} must be set in production"]
    assert weak.value.problems == [f"{variable} must not be a known default value in production"]


@pytest.mark.usefixtures("owner_environment")
def test_owner_jobs_are_not_held_to_the_api_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")

    owner = load_settings(env_file=None, owner=True)
    assert owner.runtime.demo_mode is True
    assert owner.langfuse.enabled
    with pytest.raises(SettingsError) as raised:
        load_settings(env_file=None)
    assert "LANGFUSE_PUBLIC_KEY must be set when LANGFUSE_ENABLED=true" in raised.value.problems


@pytest.mark.parametrize(
    "base",
    ["http://ollama:11434", "http://host.docker.internal:11434", "http://10.0.0.5:11434", "http://127.0.0.1:11434"],
)
def test_production_accepts_a_private_http_model_base_only_when_allowed(
    production_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch, base: str
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "litellm")
    monkeypatch.setenv("LLM_PRIMARY_MODEL", "ollama/qwen2.5:7b-instruct")
    monkeypatch.setenv("LLM_API_BASE", base)
    with pytest.raises(SettingsError) as refused:
        load_settings(env_file=None)
    monkeypatch.setenv("LLM_ALLOW_PRIVATE_HTTP_BASE", "true")

    settings = load_settings(env_file=None)

    assert "LLM_API_BASE must use https in production" in refused.value.problems
    assert "LLM_API_KEY_PRIMARY must be set in production" in refused.value.problems
    assert settings.llm.api_base == base


@pytest.mark.parametrize("base", ["http://api.example.com/v1", "http://203.0.113.9:11434", "ftp://ollama:11434"])
def test_the_private_http_exception_never_covers_a_public_host(
    production_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch, base: str
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "litellm")
    monkeypatch.setenv("LLM_API_BASE", base)
    monkeypatch.setenv("LLM_ALLOW_PRIVATE_HTTP_BASE", "true")

    with pytest.raises(SettingsError) as raised:
        load_settings(env_file=None)

    assert raised.value.problems == [
        "LLM_API_BASE must use https in production (plain http only with LLM_ALLOW_PRIVATE_HTTP_BASE=true "
        "and a private host)",
        "LLM_API_KEY_PRIMARY must be set in production",
    ]


def test_a_hosted_https_provider_is_a_settings_only_change(
    production_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "litellm")
    monkeypatch.setenv("LLM_PRIMARY_MODEL", "openai/gpt-5-mini")
    monkeypatch.setenv("LLM_API_KEY_PRIMARY", _strong_secret())
    monkeypatch.setenv("LLM_API_BASE", "https://api.openai.com/v1")

    assert load_settings(env_file=None).llm.primary_model == "openai/gpt-5-mini"


def _secret_files(directory: Path, names: tuple[str, ...]) -> dict[str, str]:
    """Write one mounted-style secret file per name (with the trailing newline an editor would add)."""
    directory.mkdir(parents=True, exist_ok=True)
    values = {name: _strong_secret() for name in names}
    for name, value in values.items():
        (directory / name).write_text(value + "\n", encoding="utf-8")
    return values


@pytest.fixture
def production_with_secret_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, str]:
    """The API's production environment with every secret in SECRETS_DIR and none in the environment."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("RETRIEVAL_INDEX_SOURCE", "stored")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://bank.example")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "postgres")
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path / "secrets"))
    return _secret_files(tmp_path / "secrets", SECRET_VARIABLES)


def test_production_reads_every_secret_from_the_secrets_dir(production_with_secret_files: dict[str, str]) -> None:
    settings = load_settings(env_file=None)

    assert settings.security.session_secret is not None
    assert settings.security.session_secret.get_secret_value() == production_with_secret_files["SESSION_SECRET"]
    assert settings.security.csrf_secret is not None
    assert settings.security.csrf_secret.get_secret_value() == production_with_secret_files["CSRF_SECRET"]
    assert settings.database.app_password is not None
    assert settings.database.app_password.get_secret_value() == production_with_secret_files["POSTGRES_APP_PASSWORD"]


def test_a_missing_secret_file_is_reported_like_a_missing_variable(
    production_with_secret_files: dict[str, str], tmp_path: Path
) -> None:
    (tmp_path / "secrets" / "CSRF_SECRET").unlink()

    with pytest.raises(SettingsError) as raised:
        load_settings(env_file=None)

    assert raised.value.problems == ["CSRF_SECRET must be set in production"]


def test_a_secrets_dir_that_does_not_exist_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path / "missing"))

    with pytest.raises(SettingsError) as raised:
        load_settings(env_file=None)

    assert raised.value.problems == ["SECRETS_DIR must name an existing directory of secret files"]


@pytest.mark.parametrize("variable", ["SESSION_SECRET", "CSRF_SECRET", "POSTGRES_APP_PASSWORD"])
def test_production_with_a_secrets_dir_refuses_the_same_secret_in_the_environment(
    production_with_secret_files: dict[str, str], monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    leftover = _strong_secret()
    monkeypatch.setenv(variable, leftover)

    with pytest.raises(SettingsError) as raised:
        load_settings(env_file=None)

    assert raised.value.problems == [f"{variable} must come from SECRETS_DIR, not from the environment, in production"]
    assert leftover not in str(raised.value)


def test_development_lets_an_environment_variable_override_a_secret_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _secret_files(tmp_path / "secrets", ("SESSION_SECRET",))
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path / "secrets"))
    monkeypatch.setenv("SESSION_SECRET", "dev-only-local-override-for-a-test")

    settings = load_settings(env_file=None)

    assert settings.security.session_secret is not None
    assert settings.security.session_secret.get_secret_value() == "dev-only-local-override-for-a-test"


def test_owner_jobs_read_the_owner_password_from_the_secrets_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path / "secrets"))
    values = _secret_files(tmp_path / "secrets", ("POSTGRES_ADMIN_PASSWORD", "SESSION_SECRET"))

    settings = load_settings(env_file=None, owner=True)

    assert settings.database.admin_password is not None
    assert settings.database.admin_password.get_secret_value() == values["POSTGRES_ADMIN_PASSWORD"]
    assert settings.database.app_password is None


def test_the_secret_source_rule_reads_an_injected_environment(production_with_secret_files: dict[str, str]) -> None:
    with pytest.raises(SettingsError) as raised:
        load_settings(env_file=None, environ={"LLM_API_KEY_PRIMARY": _strong_secret()})

    assert raised.value.problems == [
        "LLM_API_KEY_PRIMARY must come from SECRETS_DIR, not from the environment, in production"
    ]


def test_retention_defaults_and_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load_settings(env_file=None)
    assert (settings.retention.conversation_days, settings.retention.session_days) == (7, 7)
    assert settings.retention.credit_application_days == 30
    assert settings.security.rate_limit_backend == "memory"
    monkeypatch.setenv("RETENTION_CONVERSATION_DAYS", "0")
    with pytest.raises(ValueError, match="conversation_days"):
        load_settings(env_file=None)
