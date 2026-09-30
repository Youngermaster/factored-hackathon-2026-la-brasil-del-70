"""ASGI entry point, outside every layer.

``bank_agent.api`` and ``bank_agent.bootstrap`` may not import each other, so this module wires them:
settings, then logging, then observability, then the container and the HTTP configuration, then the application,
which the OpenTelemetry instrumentation wraps last.

Run with ``uvicorn bank_agent.asgi:create_app --factory``.
"""

import secrets
import uuid
from dataclasses import replace
from typing import Any

import structlog
from fastapi import FastAPI

from bank_agent import __version__
from bank_agent.api.app import create_app as create_http_app
from bank_agent.api.config import RateClass, RateLimit, SecurityConfig
from bank_agent.api.provider import ApiConfig
from bank_agent.bootstrap.container import Container
from bank_agent.bootstrap.logging import configure_logging
from bank_agent.bootstrap.observability import Observability, build_observability
from bank_agent.bootstrap.settings import AppSettings, load_settings

_log = structlog.get_logger(__name__)


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


def api_config_from(settings: AppSettings, observability: Observability | None = None) -> ApiConfig:
    """HTTP configuration for the given settings. API docs are hidden in production."""
    config = ApiConfig(
        request_id_factory=_random_request_id,
        version=__version__,
        expose_docs=not settings.is_production,
        security=security_config_from(settings),
        database_retry_after_seconds=settings.degradation.database_retry_after_seconds,
    )
    if observability is None:
        return config
    return replace(config, current_trace_id=observability.telemetry.current_trace_id)


def build_app(settings: AppSettings, observability: Observability | None = None, **container: Any) -> FastAPI:
    """The instrumented application: telemetry into the container, trace ids into the HTTP layer, server spans."""
    observability = observability or build_observability(settings.observability, environment=settings.runtime.app_env)
    wired = Container(settings, telemetry=observability.telemetry, on_close=(observability.shutdown,), **container)
    app = create_http_app(wired, api_config_from(settings, observability))
    observability.instrument_app(app)
    observability.instrument_dependencies(wired.database_engine)
    return app


def warn_about_public_demo_mode(settings: AppSettings) -> bool:
    """Log once at startup when production runs the public demo (on-screen demo codes; docs/security/demo-mode.md)."""
    if not (settings.is_production and settings.runtime.demo_mode):
        return False
    _log.warning("public_demo_mode", detail="demo one-time codes are shown on screen; synthetic data only")
    return True


def create_app() -> FastAPI:
    """Build the application from the environment."""
    settings = load_settings()
    configure_logging(settings.runtime.log_level)
    warn_about_public_demo_mode(settings)
    return build_app(settings)
