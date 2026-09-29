"""The authentication routes end to end: one-time codes, sessions, step-up, logout, and cookie flags."""

from datetime import timedelta
from http.cookies import SimpleCookie

import httpx
import pytest
from fastapi import FastAPI

from bank_agent_api import DOCUMENT_MX, PHONE_MX, ApiBackend, ApiClient, production_app


def _cookie_attributes(header: str) -> dict[str, str]:
    cookie = SimpleCookie()
    cookie.load(header)
    (morsel,) = cookie.values()
    flags = {key: str(value) for key, value in morsel.items() if value}
    flags["name"] = morsel.key
    return flags


def _set_cookies(response_headers: list[tuple[str, str]]) -> dict[str, dict[str, str]]:
    found = {}
    for name, value in response_headers:
        if name.lower() == "set-cookie":
            attributes = _cookie_attributes(value)
            found[attributes["name"]] = {**attributes, "raw": value}
    return found


async def _me_with(app: FastAPI, session_token: str) -> httpx.Response:
    """``/v1/auth/me`` from another browser that replays a session token."""
    async with ApiClient(app) as other:
        other.http.cookies.set("session", session_token)
        return await other.get("/v1/auth/me")


async def test_start_verify_and_me_open_a_customer_session(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    async with ApiClient(harness.app) as client:
        assert (await client.get("/v1/auth/me")).status_code == 401
        verified = await client.login("persona-mx", language="es")
        session = verified.json()["session"]
        assert (session["role"], session["auth_level"], session["language_preference"]) == (
            "customer", "otp_verified", "es",
        )  # fmt: skip
        me = await client.get("/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["step_up_valid"] is False
    assert me.json()["absolute_expires_at"] == session["absolute_expires_at"]


async def test_document_identification_needs_the_code_too(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    async with ApiClient(harness.app) as client:
        started = await client.post(
            "/v1/auth/start", {"kind": "document", "document_number": DOCUMENT_MX, "phone_last4": PHONE_MX}
        )
        assert started.status_code == 200
        assert "session" not in {cookie.name for cookie in client.http.cookies.jar}
        assert (await client.get("/v1/auth/me")).status_code == 401
        verified = await client.post(
            "/v1/auth/verify", {"challenge_id": started.json()["challenge_id"], "code": started.json()["demo_code"]}
        )
    assert verified.status_code == 200


async def test_an_unknown_person_gets_the_same_challenge_shape_and_the_same_failure(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    async with ApiClient(harness.app) as client:
        known = await client.post("/v1/auth/start", {"kind": "persona", "persona_id": "persona-mx"})
        unknown = await client.post("/v1/auth/start", {"kind": "persona", "persona_id": "persona-nobody"})
        assert known.json().keys() == unknown.json().keys()
        failed = await client.post(
            "/v1/auth/verify", {"challenge_id": unknown.json()["challenge_id"], "code": unknown.json()["demo_code"]}
        )
        wrong = await client.post("/v1/auth/verify", {"challenge_id": known.json()["challenge_id"], "code": "000000"})
    assert failed.status_code == wrong.status_code == 401
    assert failed.json()["type"] == wrong.json()["type"]
    assert failed.json()["type"].endswith("/verification-failed")


async def test_five_wrong_codes_lock_the_subject_with_retry_after(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    async with ApiClient(harness.app) as client:
        started = await client.post("/v1/auth/start", {"kind": "persona", "persona_id": "persona-co"})
        challenge = started.json()["challenge_id"]
        statuses = []
        for _ in range(5):
            response = await client.post("/v1/auth/verify", {"challenge_id": challenge, "code": "000001"})
            statuses.append(response.status_code)
        again = await client.post("/v1/auth/start", {"kind": "persona", "persona_id": "persona-co"})
    assert statuses == [401, 401, 401, 401, 429]
    assert response.json()["type"].endswith("/identity-locked")
    assert response.headers["retry-after"] == "900"
    assert again.status_code == 429
    assert int(again.headers["retry-after"]) <= 900


async def test_an_expired_code_is_refused_with_its_own_problem_type(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    async with ApiClient(harness.app) as client:
        started = await client.post("/v1/auth/start", {"kind": "persona", "persona_id": "persona-ar"})
        harness.clock.advance(timedelta(minutes=5, seconds=1))
        expired = await client.post(
            "/v1/auth/verify", {"challenge_id": started.json()["challenge_id"], "code": started.json()["demo_code"]}
        )
    assert expired.status_code == 401
    assert expired.json()["type"].endswith("/code-expired")


async def test_the_demo_code_is_shown_only_in_demo_mode(
    api_backend: ApiBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEMO_MODE", "false")
    harness = api_backend.build()
    async with ApiClient(harness.app) as client:
        started = await client.post("/v1/auth/start", {"kind": "persona", "persona_id": "persona-mx"})
    assert started.status_code == 200
    assert started.json()["demo_code"] is None
    assert started.json()["delivery_channel"] == "sms"


async def test_step_up_rotates_the_session_and_the_csrf_token_and_opens_a_window(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    async with ApiClient(harness.app) as client:
        await client.login("persona-co")
        old_session = client.http.cookies.get("session")
        old_csrf = client.csrf_token
        stepped = await client.step_up()
        assert stepped.json()["session"]["step_up_valid"] is True
        assert stepped.json()["session"]["auth_level"] == "step_up"
        assert client.http.cookies.get("session") != old_session
        assert client.csrf_token != old_csrf
        assert (await _me_with(harness.app, str(old_session))).status_code == 401
        harness.clock.advance(timedelta(minutes=6))
        me = await client.get("/v1/auth/me")
    assert me.json()["step_up_valid"] is False


async def test_logout_revokes_clears_the_cookie_and_returns_an_anonymous_token(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    async with ApiClient(harness.app) as client:
        await client.login("persona-mx")
        token = client.http.cookies.get("session")
        logged_out = await client.post("/v1/auth/logout")
        assert logged_out.status_code == 200
        assert client.http.cookies.get("session") is None
    assert (await _me_with(harness.app, str(token))).status_code == 401


async def test_sessions_expire_when_idle_and_the_problem_says_so(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    async with ApiClient(harness.app) as client:
        await client.login("persona-mx")
        harness.clock.advance(timedelta(minutes=16))
        me = await client.get("/v1/auth/me")
    assert me.status_code == 401
    assert me.json()["type"].endswith("/session-expired")


async def test_development_cookie_flags(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    async with ApiClient(harness.app) as client:
        csrf = await client.http.get("/v1/auth/csrf")
        client.csrf_token = csrf.json()["csrf_token"]
        started = await client.post("/v1/auth/start", {"kind": "persona", "persona_id": "persona-mx"})
        verified = await client.post(
            "/v1/auth/verify", {"challenge_id": started.json()["challenge_id"], "code": started.json()["demo_code"]}
        )
    cookies = _set_cookies(verified.headers.multi_items())
    session = cookies["session"]
    assert session["httponly"]
    assert session["samesite"] == "strict"
    assert session["path"] == "/"
    assert "secure" not in session
    assert 0 < int(session["max-age"]) <= 3600
    assert "httponly" not in cookies["csrf"]
    assert cookies["csrf"]["samesite"] == "strict"


async def test_production_cookies_use_the_host_prefix_and_are_secure(api_backend: ApiBackend) -> None:
    app = production_app(api_backend.build())
    async with ApiClient(app, https=True) as client:
        csrf = await client.http.get("/v1/auth/csrf")
        client.csrf_token = csrf.json()["csrf_token"]
        started = await client.post("/v1/auth/start", {"kind": "persona", "persona_id": "persona-mx"})
        verified = await client.post(
            "/v1/auth/verify", {"challenge_id": started.json()["challenge_id"], "code": started.json()["demo_code"]}
        )
        me = await client.get("/v1/auth/me")
    cookies = {**_set_cookies(csrf.headers.multi_items()), **_set_cookies(verified.headers.multi_items())}
    session, csrf_cookie = cookies["__Host-session"], cookies["__Host-csrf"]
    for cookie in (session, csrf_cookie):
        assert cookie["secure"]
        assert cookie["samesite"] == "strict"
        assert cookie["path"] == "/"
        assert "domain" not in cookie
    assert session["httponly"]
    assert "httponly" not in csrf_cookie
    assert me.status_code == 200
    assert "strict-transport-security" in me.headers


async def test_a_lost_session_answer_also_deletes_the_stale_cookie(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    async with ApiClient(harness.app) as client:
        await client.login("persona-mx")
        harness.clock.advance(timedelta(minutes=16))
        expired = await client.get("/v1/auth/me")
        assert expired.json()["type"].endswith("/session-expired")
        cleared = _set_cookies(expired.headers.multi_items())["session"]
        assert cleared["max-age"] == "0"
        assert client.http.cookies.get("session") is None
    unknown = await _me_with(harness.app, "not-a-live-session-token")
    assert unknown.json()["type"].endswith("/authentication-required")
    assert "session" in _set_cookies(unknown.headers.multi_items())


async def test_other_401s_keep_the_session_cookie(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    async with ApiClient(harness.app) as client:
        assert "set-cookie" not in (await client.get("/v1/auth/me")).headers
        await client.login("persona-mx")
        challenge = await client.post("/v1/auth/step-up/start")
        wrong = await client.post(
            "/v1/auth/step-up/verify", {"challenge_id": challenge.json()["challenge_id"], "code": "000000"}
        )
        assert wrong.json()["type"].endswith("/verification-failed")
        assert "session" not in _set_cookies(wrong.headers.multi_items())
        assert (await client.get("/v1/auth/me")).status_code == 200
