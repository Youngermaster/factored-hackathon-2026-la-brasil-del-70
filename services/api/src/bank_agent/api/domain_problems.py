"""The one place where domain error families become RFC 9457 problem types.

Families map to a status code and a stable problem type; the error message is never exposed. A few errors
get their own problem type because clients act on them differently (an expired session, a required step-up).
Phase 11 refines individual codes (for example 429 with ``Retry-After`` for a lockout) here, never in routers.
"""

from typing import Final

from bank_agent.api.problems import INTERNAL_PROBLEM, ProblemRegistry, ProblemType
from bank_agent.domain.errors import (
    AccessContextError,
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    ConflictError,
    DependencyError,
    DomainError,
    InvariantViolationError,
    NotFoundError,
    SessionExpiredError,
    StateTransitionError,
    StepUpRequiredError,
)

DOMAIN_PROBLEMS: Final[tuple[tuple[type[DomainError], ProblemType], ...]] = (
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
        registry.register(error_type, problem)
    return registry


def domain_problem_registry() -> ProblemRegistry:
    """A new registry with every domain error family registered."""
    return register_domain_problems(ProblemRegistry())
