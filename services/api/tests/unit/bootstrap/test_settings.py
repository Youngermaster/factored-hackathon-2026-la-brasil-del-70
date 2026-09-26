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
    values = {"APP_ENV": "production", "DEMO_MODE": "false"}
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

    assert len(raised.value.problems) == 1 + len(SECRET_VARIABLES)


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


def test_database_is_configured_once_the_application_password_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_APP_PASSWORD", _strong_secret())

    assert load_settings(env_file=None).database.is_configured
