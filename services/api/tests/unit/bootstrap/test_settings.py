import secrets
from decimal import Decimal
from pathlib import Path

import pytest

from bank_agent.bootstrap.settings import MIN_SECRET_LENGTH, SettingsError, load_settings

SECRET_VARIABLES = ("SESSION_SECRET", "CSRF_SECRET", "POSTGRES_ADMIN_PASSWORD", "POSTGRES_APP_PASSWORD")


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

    assert raised.value.problems == ["DEMO_MODE must be false in production"]


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

    assert len(raised.value.problems) == 3 + len(SECRET_VARIABLES)
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
