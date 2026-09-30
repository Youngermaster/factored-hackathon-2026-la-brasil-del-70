"""FastAPI dependencies: services, the session from the cookie, roles, CSRF, and rate limits.

Every route declares its access through ``endpoint(...)``: the rate class, whether it changes state (and so needs a
CSRF token), and the roles that may call it. The same call puts ``x-roles``, ``x-rate-limit``, and ``x-csrf`` on
the OpenAPI operation, and a unit test checks that the role a route enforces equals the role it documents.
Dependencies run in this order: rate limit, CSRF, then the session and its role.
"""

from collections.abc import Awaitable, Callable, Iterable
from functools import cache
from typing import Any, Final

from fastapi import Depends, Request

from bank_agent.api.config import RateClass, SecurityConfig
from bank_agent.api.csrf import CSRF_HEADER, CsrfTokens
from bank_agent.api.errors import (
    CsrfTokenError,
    NotAuthenticatedError,
    RateLimitedError,
    RoleNotPermittedError,
    ServiceUnavailableError,
)
from bank_agent.api.metrics import HttpMetrics
from bank_agent.api.provider import ApiConfig, ServiceProvider
from bank_agent.api.ratelimit import RateLimiter
from bank_agent.application.identity.sessions import SessionService
from bank_agent.domain.access import Role
from bank_agent.domain.errors import SessionNotFoundError
from bank_agent.domain.session import Session

ANYONE: Final = "anyone"
MAX_COOKIE_LENGTH: Final = 256
SIGNED_IN: Final = frozenset(Role)


def services(request: Request) -> ServiceProvider:
    provider: ServiceProvider = request.app.state.provider
    return provider


def security_config(request: Request) -> SecurityConfig:
    config: ApiConfig = request.app.state.api_config
    return config.security


def session_token(request: Request) -> str | None:
    token = request.cookies.get(security_config(request).cookies.session)
    if not token or len(token) > MAX_COOKIE_LENGTH:
        return None
    return token


def client_ip(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


def session_service(request: Request) -> SessionService:
    service = services(request).session_service
    if service is None:
        raise ServiceUnavailableError("identity needs SESSION_SECRET")
    return service


async def current_session(request: Request) -> Session:
    """The live session of the cookie. No cookie, an unknown token, or an expired or revoked session is a 401."""
    token = session_token(request)
    if token is None:
        raise NotAuthenticatedError("no session cookie")
    try:
        session = await session_service(request).resolve(token)
    except SessionNotFoundError:
        raise NotAuthenticatedError("unknown session") from None
    metrics: HttpMetrics = request.app.state.http_metrics
    metrics.session_seen(session, services(request).clock.now())
    return session


@cache
def role_dependency(roles: frozenset[Role]) -> Callable[[Request], Awaitable[Session]]:
    """One dependency per role set, cached so a route's declaration and its parameter share one resolution."""

    async def require(request: Request) -> Session:
        session = await current_session(request)
        if session.role not in roles:
            raise RoleNotPermittedError(f"role {session.role.value} is not permitted")
        return session

    require.roles = roles  # type: ignore[attr-defined]
    return require


def require_csrf(request: Request) -> None:
    tokens: CsrfTokens = request.app.state.csrf
    accepted = tokens.accepts(
        header=request.headers.get(CSRF_HEADER),
        cookie=request.cookies.get(security_config(request).cookies.csrf),
        session_token=session_token(request),
    )
    if not accepted:
        raise CsrfTokenError("missing or invalid CSRF token")


@cache
def rate_limit(rate_class: RateClass) -> Callable[[Request], Awaitable[None]]:
    async def check(request: Request) -> None:
        limiter: RateLimiter = request.app.state.rate_limiter
        limit = security_config(request).rate_limits[rate_class]
        try:
            await limiter.check(rate_class, limit, client_ip=client_ip(request), session_token=session_token(request))
        except RateLimitedError as refused:
            metrics: HttpMetrics = request.app.state.http_metrics
            metrics.rate_limited(rate_class, refused.key)
            raise

    return check


def endpoint(
    *,
    rate: RateClass,
    roles: Iterable[Role] | None,
    changes_state: bool,
    operation_id: str,
    access: Callable[..., Awaitable[None]] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Keyword arguments for a route decorator: dependencies and OpenAPI extensions.

    ``roles=None`` is public unless ``access`` (a dependency with a ``roles`` attribute) decides at request time.
    """
    dependencies: list[Any] = [Depends(rate_limit(rate))]
    if changes_state:
        dependencies.append(Depends(require_csrf))
    if access is not None:
        dependencies.append(Depends(access))
    if roles is not None:
        dependencies.append(Depends(role_dependency(frozenset(roles))))
    documented = sorted(role.value for role in roles) if roles is not None else [ANYONE]
    openapi_extra = {"x-roles": documented, "x-rate-limit": rate.value, "x-csrf": changes_state}
    openapi_extra.update(extra.pop("openapi_extra", {}))
    return {"dependencies": dependencies, "openapi_extra": openapi_extra, "operation_id": operation_id, **extra}
