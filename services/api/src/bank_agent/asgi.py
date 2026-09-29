"""ASGI entry point, outside every layer.

``bank_agent.api`` and ``bank_agent.bootstrap`` may not import each other, so this module wires them:
settings, then logging, then the container and the HTTP configuration, then the application.

Run with ``uvicorn bank_agent.asgi:create_app --factory``.
"""

import secrets
import uuid

from fastapi import FastAPI

from bank_agent import __version__
from bank_agent.api.app import create_app as create_http_app
from bank_agent.api.config import RateClass, RateLimit, SecurityConfig
from bank_agent.api.provider import ApiConfig
from bank_agent.bootstrap.container import Container
from bank_agent.bootstrap.logging import configure_logging
from bank_agent.bootstrap.settings import AppSettings, load_settings


def _random_request_id() -> str:
    return uuid.uuid4().hex


def security_config_from(settings: AppSettings) -> SecurityConfig:
    """Cookies, CSRF, CORS, body size, and rate limits from settings.

    Without ``CSRF_SECRET`` (development only; production refuses to start) tokens are signed with a random
    per-process secret, so they stop working when the process restarts.
    """
    security = settings.security
    secret = security.csrf_secret.get_secret_value().strip() if security.csrf_secret is not None else ""
    return SecurityConfig(
        production=settings.is_production,
        csrf_secret=secret.encode("utf-8") if secret else secrets.token_bytes(32),
        cors_allowed_origins=tuple(security.cors_allowed_origins),
        max_request_body_bytes=security.max_request_body_bytes,
        rate_limits={
            RateClass.AUTH: RateLimit(security.rate_limit_auth_per_minute, security.rate_limit_session_auth_per_minute),
            RateClass.WRITE: RateLimit(
                security.rate_limit_write_per_minute, security.rate_limit_session_write_per_minute
            ),
            RateClass.READ: RateLimit(security.rate_limit_read_per_minute, security.rate_limit_session_read_per_minute),
        },
        eval_summaries_public=settings.evaluation.summaries_public,
    )


def api_config_from(settings: AppSettings) -> ApiConfig:
    """HTTP configuration for the given settings. API docs are hidden in production."""
    return ApiConfig(
        request_id_factory=_random_request_id,
        version=__version__,
        expose_docs=not settings.is_production,
        security=security_config_from(settings),
    )


def create_app() -> FastAPI:
    """Build the application from the environment."""
    settings = load_settings()
    configure_logging(settings.runtime.log_level)
    return create_http_app(Container(settings), api_config_from(settings))
