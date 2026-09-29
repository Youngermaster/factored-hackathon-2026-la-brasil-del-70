"""Setting and clearing the session and CSRF cookies with the flags CLAUDE.md section 7 requires.

Production: ``__Host-session`` and ``__Host-csrf``, both ``Secure``, ``SameSite=Strict``, ``Path=/``, no ``Domain``;
the session cookie is also ``HttpOnly``. Development and test use ``session`` and ``csrf`` with the same flags
except ``Secure``, because the local servers speak plain http (the ``__Host-`` prefix requires ``Secure``).
"""

from typing import Final

from starlette.requests import Request
from starlette.responses import Response

from bank_agent.api.config import SecurityConfig
from bank_agent.api.problems import ProblemType
from bank_agent.api.provider import ApiConfig

# The problems that mean the session cookie no longer names a live session.
LOST_SESSION_SLUGS: Final = frozenset({"authentication-required", "session-expired"})


def set_session_cookie(response: Response, config: SecurityConfig, token: str, max_age_seconds: int) -> None:
    """Set the session cookie; it expires with the server session's absolute expiry."""
    response.set_cookie(
        config.cookies.session,
        token,
        max_age=max(0, max_age_seconds),
        path="/",
        secure=config.secure_cookies,
        httponly=True,
        samesite="strict",
    )


def clear_session_cookie(response: Response, config: SecurityConfig) -> None:
    response.delete_cookie(
        config.cookies.session, path="/", secure=config.secure_cookies, httponly=True, samesite="strict"
    )


def set_csrf_cookie(response: Response, config: SecurityConfig, token: str) -> None:
    """Set the double-submit cookie. It is readable by scripts on purpose; it proves nothing on its own."""
    response.set_cookie(
        config.cookies.csrf,
        token,
        path="/",
        secure=config.secure_cookies,
        httponly=False,
        samesite="strict",
    )


def clear_lost_session_cookie(request: Request, problem: ProblemType, response: Response) -> None:
    """Problem response hook: a 401 for an unknown, revoked, or expired session also deletes its cookie.

    Only when the request carried one, and never for other 401s: a wrong one-time code during step-up must not end
    the live session it was meant to strengthen.
    """
    if problem.slug not in LOST_SESSION_SLUGS:
        return
    config: ApiConfig = request.app.state.api_config
    if request.cookies.get(config.security.cookies.session):
        clear_session_cookie(response, config.security)
