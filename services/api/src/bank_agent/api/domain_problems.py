"""The one place where domain error families become RFC 9457 problem types.

Families map to a status code and a stable problem type; the error message is never exposed. A few errors
get their own problem type because clients act on them differently (an expired session, a required step-up).
Phase 11 refines individual codes (for example 429 with ``Retry-After`` for a lockout) here, never in routers.
"""

import math
from typing import Final

from bank_agent.api.errors import (
    CsrfTokenError,
    NotAuthenticatedError,
    PayloadTooLargeError,
    RateLimitedError,
    RoleNotPermittedError,
    ServiceUnavailableError,
)
from bank_agent.api.problems import INTERNAL_PROBLEM, PAYLOAD_TOO_LARGE_PROBLEM, ProblemRegistry, ProblemType
from bank_agent.domain.errors import (
    AccessContextError,
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    ConflictError,
    ConversationCreationLimitedError,
    DatabaseUnavailableError,
    DependencyError,
    DomainError,
    IdentityChallengeExpiredError,
    IdentityChallengeFailedError,
    IdentityLockedError,
    InvariantViolationError,
    NotFoundError,
    SessionExpiredError,
    StateTransitionError,
    StepUpRequiredError,
)

DOMAIN_PROBLEMS: Final[tuple[tuple[type[DomainError], ProblemType], ...]] = (
    (ConversationCreationLimitedError, ProblemType(429, "conversation-creation-limited", "Too many new conversations")),
    (NotFoundError, ProblemType(404, "resource-not-found", "Resource not found")),
    (AuthenticationError, ProblemType(401, "authentication-required", "Authentication required")),
    (SessionExpiredError, ProblemType(401, "session-expired", "Session expired")),
    (AuthorizationError, ProblemType(403, "action-not-permitted", "Action not permitted")),
    (StepUpRequiredError, ProblemType(403, "step-up-required", "Step-up authentication required")),
    (AccessContextError, INTERNAL_PROBLEM),
    (ConflictError, ProblemType(409, "conflict", "The request conflicts with the current state")),
    (StateTransitionError, ProblemType(409, "invalid-state-transition", "Invalid state transition")),
    (InvariantViolationError, ProblemType(422, "unprocessable-request", "The request cannot be processed")),
    (DependencyError, ProblemType(503, "dependency-unavailable", "A dependency is temporarily unavailable")),
    (ConfigurationError, INTERNAL_PROBLEM),
)


def register_domain_problems(registry: ProblemRegistry) -> ProblemRegistry:
    """Register every domain error family on ``registry`` and return it."""
    for error_type, problem in DOMAIN_PROBLEMS:
        registry.register(
            error_type, problem, headers=_retry_after if error_type is ConversationCreationLimitedError else None
        )
    return registry


def domain_problem_registry() -> ProblemRegistry:
    """A new registry with every domain error family registered."""
    return register_domain_problems(ProblemRegistry())


def _retry_after(exception: Exception) -> dict[str, str]:
    if isinstance(exception, RateLimitedError):
        return {"Retry-After": str(exception.retry_after_seconds)}
    if isinstance(exception, IdentityLockedError | ConversationCreationLimitedError):
        return {"Retry-After": str(max(1, math.ceil(exception.retry_after.total_seconds())))}
    return {}


RATE_LIMITED_PROBLEM: Final = ProblemType(429, "rate-limited", "Too many requests")
CSRF_PROBLEM: Final = ProblemType(403, "csrf-token-invalid", "Missing or invalid CSRF token")
AUTHENTICATION_REQUIRED_PROBLEM: Final = ProblemType(401, "authentication-required", "Authentication required")

HTTP_PROBLEMS: Final[tuple[tuple[type[Exception], ProblemType], ...]] = (
    (CsrfTokenError, CSRF_PROBLEM),
    (NotAuthenticatedError, AUTHENTICATION_REQUIRED_PROBLEM),
    (RoleNotPermittedError, ProblemType(403, "role-not-permitted", "Not permitted for this role")),
    (PayloadTooLargeError, PAYLOAD_TOO_LARGE_PROBLEM),
    (RateLimitedError, RATE_LIMITED_PROBLEM),
    (ServiceUnavailableError, ProblemType(503, "service-unavailable", "The service is not configured")),
    (IdentityLockedError, ProblemType(429, "identity-locked", "Too many failed attempts; try again later")),
    (IdentityChallengeFailedError, ProblemType(401, "verification-failed", "The verification failed")),
    (IdentityChallengeExpiredError, ProblemType(401, "code-expired", "The one-time code expired")),
)
"""HTTP-layer errors and the identity errors clients act on differently (resend, wait). Registered before the
domain families, so the most specific entry wins."""


DEPENDENCY_PROBLEM: Final = ProblemType(503, "dependency-unavailable", "A dependency is temporarily unavailable")


def api_problem_registry(database_retry_after_seconds: int = 30) -> ProblemRegistry:
    """The registry ``create_app`` installs: the HTTP-layer errors, the identity refinements, and the families.

    An unavailable database (degradation level L4) is the dependency problem with ``Retry-After``: nothing was done,
    and the client may send the same request again (turns are idempotent by ``turn_id``).
    """
    registry = ProblemRegistry()
    for error_type, problem in HTTP_PROBLEMS:
        needs_retry_after = problem.status == 429
        registry.register(error_type, problem, headers=_retry_after if needs_retry_after else None)
    retry_after = {"Retry-After": str(database_retry_after_seconds)}
    registry.register(DatabaseUnavailableError, DEPENDENCY_PROBLEM, headers=lambda _: dict(retry_after))
    return register_domain_problems(registry)
