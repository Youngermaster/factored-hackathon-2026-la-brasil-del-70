"""Errors raised by the HTTP layer itself (not by the domain). ``problems.py`` maps each to a problem type."""

import math


class ApiError(Exception):
    """Base class. Messages are for logs only; clients see the problem type."""


class CsrfTokenError(ApiError):
    """A state-changing request without a valid double-submit token for its session."""


class NotAuthenticatedError(ApiError):
    """No session cookie, or one that resolves to no session."""


class RoleNotPermittedError(ApiError):
    """The session's role may not call this operation."""


class PayloadTooLargeError(ApiError):
    """The request body exceeds the configured limit."""


class RateLimitedError(ApiError):
    """Too many requests in the current window for this rate class."""

    def __init__(self, retry_after_seconds: float) -> None:
        super().__init__("rate limited")
        self.retry_after_seconds = max(1, math.ceil(retry_after_seconds))


class ServiceUnavailableError(ApiError):
    """A service this operation needs is not configured (for example identity without ``SESSION_SECRET``)."""
