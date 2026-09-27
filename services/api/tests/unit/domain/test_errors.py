import re
from datetime import timedelta

from bank_agent.domain.errors import (
    DomainError,
    IdentityLockedError,
    LlmTimeoutError,
    NotFoundError,
    SessionExpiredError,
    ToolPermanentError,
    all_error_types,
)


def test_every_error_code_is_unique_and_snake_case() -> None:
    codes = [error_type.code for error_type in all_error_types() if error_type.__module__ == "bank_agent.domain.errors"]
    assert len(codes) == len(set(codes))
    assert all(re.fullmatch(r"[a-z][a-z0-9_]*", code) for code in codes)
    assert len(codes) > 40


def test_default_message_is_the_code_in_words() -> None:
    assert str(NotFoundError()) == "not found"


def test_retryable_flags() -> None:
    assert LlmTimeoutError.retryable
    assert not ToolPermanentError.retryable
    assert not DomainError.retryable


def test_errors_carry_structured_details_without_input_values() -> None:
    expired = SessionExpiredError("idle")
    assert expired.reason == "idle"
    locked = IdentityLockedError(timedelta(minutes=5))
    assert locked.retry_after == timedelta(minutes=5)
    assert "5" not in str(locked)
