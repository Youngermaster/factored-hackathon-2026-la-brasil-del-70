"""Fixtures shared by every bank_agent test."""

import os
from pathlib import Path

import pytest

_SETTINGS_PREFIXES = (
    "APP_ENV",
    "DEMO_MODE",
    "LOG_LEVEL",
    "POSTGRES_",
    "SESSION_SECRET",
    "CSRF_SECRET",
    "CORS_ALLOWED_ORIGINS",
    "LLM_",
    "OTEL_",
    "POLICY_",
    "RETRIEVAL_",
)


@pytest.fixture(autouse=True)
def isolated_settings_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Remove every settings variable and run from an empty directory.

    Tests therefore never see the developer's shell environment or a local ``.env`` file, and each test
    states the environment it needs explicitly.
    """
    for name in list(os.environ):
        if name.upper().startswith(_SETTINGS_PREFIXES):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
