"""``/v1/auth``: one-time-code login, step-up, logout, the session status, and the CSRF token.

Identification alone never creates a session: ``start`` only opens a challenge, and only ``verify`` with the right
code sets the session cookie. Login and step-up rotate both the session token and the CSRF token; logout revokes
the session, clears the cookie, and hands back an anonymous CSRF token.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from bank_agent.api.config import RateClass
from bank_agent.api.cookies import clear_session_cookie, set_csrf_cookie, set_session_cookie
from bank_agent.api.csrf import CsrfTokens, binding_for
from bank_agent.api.dependencies import (
    SIGNED_IN,
    endpoint,
    role_dependency,
    security_config,
    services,
    session_service,
    session_token,
)
from bank_agent.api.errors import NotAuthenticatedError
from bank_agent.api.schemas.auth import (
    ChallengeResponse,
    CsrfResponse,
    SessionView,
    SignedInResponse,
    StartLoginRequest,
    VerifyLoginRequest,
    VerifyStepUpRequest,
)
from bank_agent.application.identity.sessions import IssuedSession
from bank_agent.domain.errors import AuthenticationError, SessionNotFoundError
from bank_agent.domain.identity import DocumentIdentification, OtpChallenge, PersonaIdentification
from bank_agent.domain.session import Session

router = APIRouter(prefix="/v1/auth", tags=["auth"])
SignedInSession = Annotated[Session, Depends(role_dependency(SIGNED_IN))]


def session_view(session: Session, now: datetime) -> SessionView:
    return SessionView(
        role=session.role,
        auth_level=session.effective_auth_level(now),
        step_up_valid=session.step_up_valid(now),
        step_up_expires_at=session.step_up_expires_at if session.step_up_valid(now) else None,
        idle_expires_at=session.idle_expires_at,
        absolute_expires_at=session.absolute_expires_at,
        language_preference=session.language_preference,
    )


def _challenge(challenge: OtpChallenge) -> ChallengeResponse:
    return ChallengeResponse(
        challenge_id=challenge.challenge_id,
        purpose=challenge.purpose,
        expires_at=challenge.expires_at,
        attempts_remaining=challenge.attempts_remaining,
        delivery_channel=challenge.delivery.channel,
        demo_code=challenge.delivery.demo_code,
    )


def _issue_csrf(request: Request, response: Response, session_token_value: str | None) -> str:
    tokens: CsrfTokens = request.app.state.csrf
    token = tokens.issue(binding_for(session_token_value))
    set_csrf_cookie(response, security_config(request), token)
    return token


def _signed_in(request: Request, response: Response, issued: IssuedSession) -> SignedInResponse:
    now = services(request).clock.now()
    remaining = int((issued.session.absolute_expires_at - now).total_seconds())
    set_session_cookie(response, security_config(request), issued.token, remaining)
    csrf = _issue_csrf(request, response, issued.token)
    return SignedInResponse(session=session_view(issued.session, now), csrf_token=csrf)


async def _revoke_quietly(request: Request, token: str | None) -> None:
    if token is None:
        return
    try:
        await session_service(request).logout(token)
    except (SessionNotFoundError, AuthenticationError):
        return


_AUTH_CSRF = endpoint(rate=RateClass.AUTH, roles=None, changes_state=False, operation_id="auth_csrf")


@router.get("/csrf", response_model=CsrfResponse, **_AUTH_CSRF)
async def csrf_token(request: Request, response: Response) -> CsrfResponse:
    """A double-submit token bound to the current session cookie, or anonymous before login."""
    return CsrfResponse(csrf_token=_issue_csrf(request, response, session_token(request)))


_AUTH_START = endpoint(rate=RateClass.AUTH, roles=None, changes_state=True, operation_id="auth_start")


@router.post("/start", response_model=ChallengeResponse, **_AUTH_START)
async def start_login(request: Request, body: StartLoginRequest) -> ChallengeResponse:
    """Open a one-time-code challenge. Unknown people get an indistinguishable challenge that never succeeds."""
    identification = (
        PersonaIdentification(persona_id=body.persona_id)
        if body.kind == "persona"
        else DocumentIdentification(document_number=body.document_number, phone_last4=body.phone_last4)
    )
    return _challenge(await session_service(request).start_login(identification))


_AUTH_VERIFY = endpoint(rate=RateClass.AUTH, roles=None, changes_state=True, operation_id="auth_verify")


@router.post("/verify", response_model=SignedInResponse, **_AUTH_VERIFY)
async def verify_login(request: Request, response: Response, body: VerifyLoginRequest) -> SignedInResponse:
    """Verify the code and start a session; any previous session of this browser is revoked."""
    issued = await session_service(request).complete_login(body.challenge_id, body.code, body.language)
    await _revoke_quietly(request, session_token(request))
    return _signed_in(request, response, issued)


_AUTH_STEP_UP_START = endpoint(
    rate=RateClass.AUTH, roles=SIGNED_IN, changes_state=True, operation_id="auth_step_up_start"
)


@router.post("/step-up/start", response_model=ChallengeResponse, **_AUTH_STEP_UP_START)
async def start_step_up(request: Request, session: SignedInSession) -> ChallengeResponse:
    """Open a step-up challenge bound to this session (needed before a write action)."""
    token = session_token(request)
    if token is None:
        raise NotAuthenticatedError("no session cookie")
    return _challenge(await session_service(request).start_step_up(token))


_AUTH_STEP_UP_VERIFY = endpoint(
    rate=RateClass.AUTH, roles=SIGNED_IN, changes_state=True, operation_id="auth_step_up_verify"
)


@router.post("/step-up/verify", response_model=SignedInResponse, **_AUTH_STEP_UP_VERIFY)
async def verify_step_up(
    request: Request, response: Response, body: VerifyStepUpRequest, session: SignedInSession
) -> SignedInResponse:
    """Verify the step-up code; the session rotates (new token, same lineage) and a step-up window opens."""
    token = session_token(request)
    if token is None:
        raise NotAuthenticatedError("no session cookie")
    issued = await session_service(request).complete_step_up(token, body.challenge_id, body.code)
    return _signed_in(request, response, issued)


_AUTH_LOGOUT = endpoint(rate=RateClass.AUTH, roles=None, changes_state=True, operation_id="auth_logout")


@router.post("/logout", response_model=CsrfResponse, **_AUTH_LOGOUT)
async def logout(request: Request, response: Response) -> CsrfResponse:
    """Revoke the session (when there is one), clear the cookie, and return an anonymous CSRF token."""
    await _revoke_quietly(request, session_token(request))
    clear_session_cookie(response, security_config(request))
    return CsrfResponse(csrf_token=_issue_csrf(request, response, None))


_AUTH_ME = endpoint(rate=RateClass.READ, roles=SIGNED_IN, changes_state=False, operation_id="auth_me")


@router.get("/me", response_model=SessionView, **_AUTH_ME)
async def me(request: Request, session: SignedInSession) -> SessionView:
    """The session's role, authentication level, expiry instants, and language preference."""
    return session_view(session, services(request).clock.now())
