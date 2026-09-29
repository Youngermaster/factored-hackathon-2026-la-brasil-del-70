"""Signed double-submit CSRF tokens."""

import secrets

from bank_agent.api.csrf import ANONYMOUS_BINDING, MAX_TOKEN_LENGTH, CsrfTokens, binding_for

SECRET = b"unit-test-csrf-secret-0123456789"

TOKEN = secrets.token_urlsafe(32)
OTHER = secrets.token_urlsafe(32)


def test_a_token_is_valid_only_for_the_binding_it_was_issued_for() -> None:
    tokens = CsrfTokens(SECRET)
    token = tokens.issue(binding_for("session-token-a"))

    assert tokens.is_valid(token, binding_for("session-token-a"))
    assert not tokens.is_valid(token, binding_for("session-token-b"))
    assert not tokens.is_valid(token, ANONYMOUS_BINDING)


def test_anonymous_tokens_bind_to_no_session_and_rotate_on_every_issue() -> None:
    tokens = CsrfTokens(SECRET)
    first, second = tokens.issue(binding_for(None)), tokens.issue(binding_for(""))

    assert first != second
    assert tokens.is_valid(first, ANONYMOUS_BINDING)
    assert tokens.is_valid(second, ANONYMOUS_BINDING)


def test_tampered_malformed_foreign_and_oversized_tokens_are_refused() -> None:
    tokens = CsrfTokens(SECRET)
    token = tokens.issue(ANONYMOUS_BINDING)
    nonce, _, signature = token.partition(".")

    assert not tokens.is_valid(f"{nonce}.{signature[:-1]}0", ANONYMOUS_BINDING)
    assert not tokens.is_valid(f"x{nonce}.{signature}", ANONYMOUS_BINDING)
    assert not tokens.is_valid(nonce, ANONYMOUS_BINDING)
    assert not tokens.is_valid(".", ANONYMOUS_BINDING)
    assert not tokens.is_valid("a" * (MAX_TOKEN_LENGTH + 1), ANONYMOUS_BINDING)
    assert not CsrfTokens(b"another-secret-of-enough-length").is_valid(token, ANONYMOUS_BINDING)


def test_the_double_submit_check_needs_the_header_equal_to_the_cookie() -> None:
    tokens = CsrfTokens(SECRET)
    token = tokens.issue(binding_for(TOKEN))

    assert tokens.accepts(header=token, cookie=token, session_token=TOKEN)
    assert not tokens.accepts(header=None, cookie=token, session_token=TOKEN)
    assert not tokens.accepts(header=token, cookie=None, session_token=TOKEN)
    assert not tokens.accepts(header=token, cookie=tokens.issue(binding_for(TOKEN)), session_token=TOKEN)
    assert not tokens.accepts(header=token, cookie=token, session_token=OTHER)
    long = "b" * (MAX_TOKEN_LENGTH + 1)
    assert not tokens.accepts(header=long, cookie=long, session_token=TOKEN)
