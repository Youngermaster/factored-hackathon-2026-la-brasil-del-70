import secrets

import pytest

from bank_agent import __version__
from bank_agent.asgi import api_config_from, create_app
from bank_agent.bootstrap.settings import SettingsError, load_settings


def test_builds_the_application_from_the_environment() -> None:
    app = create_app()

    assert app.version == __version__
    assert app.docs_url == "/docs"
    assert {"/health/live", "/health/ready"} <= set(app.openapi()["paths"])


def test_refuses_to_start_with_unsafe_production_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(SettingsError):
        create_app()


def test_production_hides_api_docs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("RETRIEVAL_INDEX_SOURCE", "stored")
    for name in ("SESSION_SECRET", "CSRF_SECRET", "POSTGRES_ADMIN_PASSWORD", "POSTGRES_APP_PASSWORD"):
        monkeypatch.setenv(name, secrets.token_urlsafe(48))

    config = api_config_from(load_settings(env_file=None))

    assert config.expose_docs is False


def test_request_ids_are_random_and_unique() -> None:
    factory = api_config_from(load_settings(env_file=None)).request_id_factory

    first, second = factory(), factory()

    assert first != second
    assert len(first) == 32
