"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from bank_agent.api.domain_problems import domain_problem_registry
from bank_agent.api.middleware import RequestIdMiddleware
from bank_agent.api.problems import ProblemRegistry
from bank_agent.api.provider import ApiConfig, ServiceProvider
from bank_agent.api.routers import health


def create_app(provider: ServiceProvider, config: ApiConfig, problems: ProblemRegistry | None = None) -> FastAPI:
    """Build the HTTP application around a service provider.

    The provider and config are stored on ``app.state`` for routers and dependencies, and the provider is
    closed when the application shuts down. ``problems`` maps typed errors to problem details; when none is
    given, a registry with every domain error family registered is used.
    """

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await provider.aclose()

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
    (problems or domain_problem_registry()).install(app)
    app.add_middleware(RequestIdMiddleware, id_factory=config.request_id_factory)
    app.include_router(health.router)
    return app
