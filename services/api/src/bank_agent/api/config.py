"""HTTP security configuration: cookies, CSRF, CORS, request size, and rate limits.

The composition root builds a ``SecurityConfig`` from settings; the API never reads the environment. Values that
depend on the environment (cookie names and the ``Secure`` flag, HSTS) are derived from ``production`` here so
that one flag decides them together.
"""

import secrets
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

DEVELOPMENT_ORIGINS: Final = ("http://localhost:5173",)


class RateClass(StrEnum):
    """Rate limit classes; authentication is the strictest."""

    AUTH = "auth"
    WRITE = "write"
    READ = "read"


@dataclass(frozen=True, slots=True)
class RateLimit:
    """Requests per minute for one rate class, per client IP and per session."""

    per_ip: int
    per_session: int


def _default_limits() -> dict[RateClass, RateLimit]:
    return {
        RateClass.AUTH: RateLimit(per_ip=10, per_session=10),
        RateClass.WRITE: RateLimit(per_ip=30, per_session=20),
        RateClass.READ: RateLimit(per_ip=120, per_session=60),
    }


@dataclass(frozen=True, slots=True)
class CookieNames:
    session: str
    csrf: str


PRODUCTION_COOKIES: Final = CookieNames(session="__Host-session", csrf="__Host-csrf")
DEVELOPMENT_COOKIES: Final = CookieNames(session="session", csrf="csrf")


@dataclass(frozen=True, slots=True)
class SecurityConfig:
    """Everything the security middleware and dependencies need.

    ``csrf_secret`` signs double-submit tokens to the session they were issued for. Production settings refuse to
    start without one; ``development`` makes a random secret per process, so tokens die with the process.
    """

    production: bool
    csrf_secret: bytes
    cors_allowed_origins: tuple[str, ...] = DEVELOPMENT_ORIGINS
    max_request_body_bytes: int = 16384
    rate_limits: dict[RateClass, RateLimit] = field(default_factory=_default_limits)
    eval_summaries_public: bool = False

    def __post_init__(self) -> None:
        if len(self.csrf_secret) < 16:
            raise ValueError("the CSRF secret must have at least 16 bytes")
        if set(self.rate_limits) != set(RateClass):
            raise ValueError("every rate class needs a limit")

    @classmethod
    def development(cls, **overrides: object) -> "SecurityConfig":
        """A development configuration with a random CSRF secret; ``overrides`` replace single fields."""
        values: dict[str, object] = {"production": False, "csrf_secret": secrets.token_bytes(32)}
        values.update(overrides)
        return cls(**values)  # type: ignore[arg-type]

    @property
    def cookies(self) -> CookieNames:
        """``__Host-`` names in production (which require ``Secure``); plain names over local http."""
        return PRODUCTION_COOKIES if self.production else DEVELOPMENT_COOKIES

    @property
    def secure_cookies(self) -> bool:
        return self.production
