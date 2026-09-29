"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, Response
from starlette.types import Scope

from bank_agent.api.cookies import clear_lost_session_cookie
from bank_agent.api.csrf import CSRF_HEADER, CsrfTokens
from bank_agent.api.domain_problems import api_problem_registry
from bank_agent.api.metrics import HttpMetrics
from bank_agent.api.middleware import (
    REQUEST_ID_HEADER,
    TRACE_ID_HEADER,
    BodySizeLimitMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
    TraceIdMiddleware,
)
from bank_agent.api.openapi import install_openapi
from bank_agent.api.problems import PAYLOAD_TOO_LARGE_PROBLEM, PROBLEM_CONTENT_TYPE, ProblemRegistry
from bank_agent.api.provider import ApiConfig, ServiceProvider
from bank_agent.api.ratelimit import SlidingWindowLimiter
from bank_agent.api.routers import agent, auth, conversations, evaluation, health, preferences


async def _payload_too_large(scope: Scope) -> Response:
    body: dict[str, object] = {
        "type": PAYLOAD_TOO_LARGE_PROBLEM.type_uri,
        "title": PAYLOAD_TOO_LARGE_PROBLEM.title,
        "status": PAYLOAD_TOO_LARGE_PROBLEM.status,
        "instance": scope.get("path", ""),
    }
    request_id = scope.get("state", {}).get("request_id")
    if request_id is not None:
        body["request_id"] = request_id
    return JSONResponse(body, status_code=PAYLOAD_TOO_LARGE_PROBLEM.status, media_type=PROBLEM_CONTENT_TYPE)


def create_app(provider: ServiceProvider, config: ApiConfig, problems: ProblemRegistry | None = None) -> FastAPI:
    """Build the HTTP application around a service provider.

    The provider and config are stored on ``app.state`` for routers and dependencies, and the provider is
    closed when the application shuts down. ``problems`` maps typed errors to problem details; when none is
    given, the HTTP-layer errors and every domain error family are registered.

    Middleware, outermost first: request id, trace id, security headers, CORS, body size limit. Every response class,
    including CORS preflights, 413 refusals, and problem details, therefore carries the security headers. The
    OpenTelemetry instrumentation, when the entry point installs it, wraps the whole stack.
    """

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await provider.aclose()

    security = config.security
    app = FastAPI(
        title=config.title,
        version=config.version,
        lifespan=lifespan,
        docs_url="/docs" if config.expose_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if config.expose_docs else None,
    )
    app.state.provider = provider
    app.state.api_config = config
    app.state.csrf = CsrfTokens(security.csrf_secret)
    app.state.rate_limiter = SlidingWindowLimiter(config.monotonic)
    app.state.http_metrics = HttpMetrics(provider.telemetry)
    registry = problems or api_problem_registry(config.database_retry_after_seconds)
    registry.install(app, response_hooks=(clear_lost_session_cookie,))
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=security.max_request_body_bytes, respond=_payload_too_large)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(security.cors_allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", CSRF_HEADER, REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER, TRACE_ID_HEADER, "Retry-After"],
        max_age=600,
    )
    app.add_middleware(SecurityHeadersMiddleware, production=security.production)
    app.add_middleware(TraceIdMiddleware, current_trace_id=config.current_trace_id)
    app.add_middleware(RequestIdMiddleware, id_factory=config.request_id_factory)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(conversations.router)
    app.include_router(preferences.router)
    app.include_router(agent.router)
    app.include_router(evaluation.router)
    install_openapi(app)
    return app
