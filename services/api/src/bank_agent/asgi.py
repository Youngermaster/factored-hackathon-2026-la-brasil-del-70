"""ASGI entry point, outside every layer.

``bank_agent.api`` and ``bank_agent.bootstrap`` may not import each other, so this module wires them:
settings, then logging, then the container and the HTTP configuration, then the application.

Run with ``uvicorn bank_agent.asgi:create_app --factory``.
"""

import uuid

from fastapi import FastAPI

from bank_agent import __version__
from bank_agent.api.app import create_app as create_http_app
from bank_agent.api.provider import ApiConfig
from bank_agent.bootstrap.container import Container
from bank_agent.bootstrap.logging import configure_logging
from bank_agent.bootstrap.settings import AppSettings, load_settings


def _random_request_id() -> str:
    return uuid.uuid4().hex


def api_config_from(settings: AppSettings) -> ApiConfig:
    """HTTP configuration for the given settings. API docs are hidden in production."""
    return ApiConfig(
        request_id_factory=_random_request_id,
        version=__version__,
        expose_docs=not settings.is_production,
    )


def create_app() -> FastAPI:
    """Build the application from the environment."""
    settings = load_settings()
    configure_logging(settings.runtime.log_level)
    return create_http_app(Container(settings), api_config_from(settings))
