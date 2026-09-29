"""Setting and clearing the session and CSRF cookies with the flags CLAUDE.md section 7 requires.

Production: ``__Host-session`` and ``__Host-csrf``, both ``Secure``, ``SameSite=Strict``, ``Path=/``, no ``Domain``;
the session cookie is also ``HttpOnly``. Development and test use ``session`` and ``csrf`` with the same flags
except ``Secure``, because the local servers speak plain http (the ``__Host-`` prefix requires ``Secure``).
"""

from starlette.responses import Response

from bank_agent.api.config import SecurityConfig


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
