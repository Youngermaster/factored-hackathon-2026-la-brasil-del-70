"""`.env.example` is a working development environment, and production refuses every dev-only value in it.

The tests copy the committed example into a temporary directory; they never read a developer's `.env`.
"""

import re
import secrets
import shutil
from pathlib import Path

import pytest
from dotenv import dotenv_values

from bank_agent.asgi import api_config_from
from bank_agent.bootstrap.settings import DEV_ONLY_SECRET_PREFIX, DEV_ONLY_SECRETS, SettingsError, load_settings

EXAMPLE = Path(__file__).resolve().parents[5] / ".env.example"
LINE = re.compile(r"^([A-Z][A-Z0-9_]*)=(\S*)")


def example_values() -> dict[str, str]:
    values = {}
    for line in EXAMPLE.read_text(encoding="utf-8").splitlines():
        match = LINE.match(line)
        if match:
            values[match.group(1)] = match.group(2)
    return values


DEV_ONLY = {name: value for name, value in example_values().items() if value.startswith(DEV_ONLY_SECRET_PREFIX)}
OWNER_ONLY = "POSTGRES_ADMIN_PASSWORD"
"""The owner password is for owner jobs only; the API process refuses it in production."""
API_DEV_ONLY = {name: value for name, value in DEV_ONLY.items() if name != OWNER_ONLY}
PRODUCTION_API = {
    "APP_ENV": "production",
    "RETRIEVAL_INDEX_SOURCE": "stored",
    "CORS_ALLOWED_ORIGINS": "https://b.example",
    "RATE_LIMIT_BACKEND": "postgres",
}


@pytest.fixture
def copied_env(tmp_path: Path) -> Path:
    target = tmp_path / ".env"
    shutil.copyfile(EXAMPLE, target)
    return target


def test_a_copy_of_the_example_loads_as_a_working_development_environment(copied_env: Path) -> None:
    settings = load_settings(env_file=copied_env)

    assert (settings.runtime.app_env, settings.runtime.demo_mode) == ("development", True)
    assert settings.llm.provider == "fake"
    assert settings.database.is_configured
    assert settings.security.session_secret is not None
    assert settings.security.cors_allowed_origins == ["http://localhost:5173"]
    assert settings.retrieval.index_source == "build"
    assert settings.workflow.enabled == ["account_inquiry", "card_support", "dispute", "credit"]
    assert api_config_from(settings).security.csrf_secret == DEV_ONLY["CSRF_SECRET"].encode()


def test_every_dev_only_placeholder_is_on_the_refused_list() -> None:
    assert set(DEV_ONLY) == {"POSTGRES_ADMIN_PASSWORD", "POSTGRES_APP_PASSWORD", "SESSION_SECRET", "CSRF_SECRET"}
    assert set(DEV_ONLY.values()) == DEV_ONLY_SECRETS
    assert all(len(value) >= 32 for value in DEV_ONLY.values())


def test_production_refuses_the_example_as_it_is(copied_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("RETRIEVAL_INDEX_SOURCE", "stored")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://bank.example")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "postgres")

    with pytest.raises(SettingsError) as raised:
        load_settings(env_file=copied_env)
    with pytest.raises(SettingsError) as owner:
        load_settings(env_file=copied_env, owner=True)

    assert sorted(raised.value.problems) == sorted(
        [
            *(f"{name} must not be a development-only value in production" for name in API_DEV_ONLY),
            "POSTGRES_ADMIN_PASSWORD must not be given to the API process in production",
        ]
    )
    assert sorted(owner.value.problems) == sorted(
        f"{name} must not be a development-only value in production" for name in (OWNER_ONLY, "SESSION_SECRET")
    )


@pytest.mark.parametrize("variable", sorted(DEV_ONLY))
def test_production_refuses_each_dev_only_secret(monkeypatch: pytest.MonkeyPatch, variable: str) -> None:
    owner = variable == OWNER_ONLY
    values = {"APP_ENV": "production"} if owner else dict(PRODUCTION_API)
    needed = (OWNER_ONLY, "SESSION_SECRET") if owner else tuple(API_DEV_ONLY)
    values.update({name: secrets.token_urlsafe(48) for name in needed})
    values[variable] = DEV_ONLY[variable]
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    with pytest.raises(SettingsError) as raised:
        load_settings(env_file=None, owner=owner)

    assert raised.value.problems == [f"{variable} must not be a development-only value in production"]


def test_any_other_dev_only_value_is_refused_too(monkeypatch: pytest.MonkeyPatch) -> None:
    values = dict(PRODUCTION_API)
    values.update({name: secrets.token_urlsafe(48) for name in API_DEV_ONLY})
    values["LLM_PROVIDER"] = "litellm"
    values["LLM_API_KEY_PRIMARY"] = "DEV-ONLY-placeholder-key-that-is-long-enough"
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    with pytest.raises(SettingsError) as raised:
        load_settings(env_file=None)

    assert raised.value.problems == ["LLM_API_KEY_PRIMARY must not be a development-only value in production"]


def test_no_value_in_the_example_parses_as_a_comment() -> None:
    parsed = dotenv_values(EXAMPLE)
    assert set(parsed) == set(example_values())
    assert [name for name, value in parsed.items() if (value or "").lstrip().startswith("#")] == []
