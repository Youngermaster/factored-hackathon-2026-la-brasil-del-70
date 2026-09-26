import pytest
from hypothesis import given
from hypothesis import strategies as st

from bank_agent.bootstrap.logging import REDACTED, RedactionProcessor, is_sensitive_key, redact, scrub_text

MASKED_KEYS = (
    "document_number",
    "email",
    "mobile_phone",
    "landline_phone",
    "address",
    "password",
    "otp",
    "token",
    "secret",
    "authorization",
    "cookie",
)


def _process(event: dict[str, object]) -> dict[str, object]:
    return dict(RedactionProcessor()(None, "info", event))


@pytest.mark.parametrize("key", MASKED_KEYS)
def test_masks_the_value_of_each_sensitive_key(key: str) -> None:
    result = _process({"event": "customer_lookup", key: "value-that-must-not-appear"})

    assert result[key] == REDACTED
    assert result["event"] == "customer_lookup"


@pytest.mark.parametrize(
    "key",
    [
        "Authorization",
        "SET-COOKIE",
        "access_token",
        "session_secret",
        "customer_email",
        "x_api_key",
        "LLM_API_KEY_PRIMARY",
        "new_password",
        "home_address",
        "otp_code",
    ],
)
def test_masks_keys_that_contain_a_sensitive_word(key: str) -> None:
    assert is_sensitive_key(key)


@pytest.mark.parametrize("key", ["event", "status", "customer_segment", "latency_ms", "footprint", "request_id"])
def test_keeps_ordinary_keys(key: str) -> None:
    assert not is_sensitive_key(key)


def test_masks_sensitive_keys_at_any_depth() -> None:
    result = _process(
        {
            "event": "x",
            "payload": {"customer": {"email": "a@b.co", "tier": "gold"}, "items": [{"token": "abc"}, {"name": "ok"}]},
        }
    )

    assert result["payload"] == {
        "customer": {"email": REDACTED, "tier": "gold"},
        "items": [{"token": REDACTED}, {"name": "ok"}],
    }


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("write to maria.perez@example.com today", "email"),
        ("CPF 123.456.789-09 on file", "document"),
        ("CNPJ 12.345.678/0001-95 on file", "document"),
        ("CURP GODE561231HDFRRN09 on file", "document"),
        ("DNI 30.123.456 on file", "document"),
        ("cedula 1.020.304.050 on file", "document"),
        ("call +57 300 123 4567 now", "phone"),
        ("call (11) 91234-5678 now", "phone"),
        ("call 55 1234 5678 now", "phone"),
        ("document 1020304050 on file", "number"),
        ("card 4111111111111111 on file", "number"),
    ],
)
def test_scrubs_sensitive_value_patterns(text: str, label: str) -> None:
    scrubbed = scrub_text(text)

    assert f"[REDACTED:{label}]" in scrubbed
    assert not any(char.isdigit() for char in scrubbed)


@pytest.mark.parametrize(
    ("original", "fragment"),
    [
        ("CPF 123.456.789-09", "123.456.789-09"),
        ("CURP GODE561231HDFRRN09", "GODE561231HDFRRN09"),
        ("DNI 30.123.456", "30.123.456"),
        ("CC 1.020.304.050", "1.020.304.050"),
        ("mail juan@banco.com.co", "juan@banco.com.co"),
    ],
)
def test_scrubbed_text_never_contains_the_original_identifier(original: str, fragment: str) -> None:
    assert fragment not in scrub_text(original)


@pytest.mark.parametrize(
    "text",
    [
        "turn completed in 1834 ms",
        "at 2026-09-26T10:22:33.123456Z",
        "case 550e8400-e29b-41d4-a716-446655440000",
        "trace 4bf92f3577b34da6a3ce929d0e0e4736",
        "rule dispute.window.v3 applied",
        "amount 125.50 USD",
        "version 1.2.3",
    ],
)
def test_keeps_ordinary_text_intact(text: str) -> None:
    assert scrub_text(text) == text


def test_scrubs_values_inside_lists_tuples_and_the_event_message() -> None:
    result = _process({"event": "sent code to ana@example.org", "recipients": ("b@example.org", "ok"), "n": 3})

    assert result["event"] == "sent code to [REDACTED:email]"
    assert result["recipients"] == ["[REDACTED:email]", "ok"]
    assert result["n"] == 3


def test_masks_large_integers_but_keeps_small_numbers_and_booleans() -> None:
    assert redact({"document": 1020304050, "count": 42, "flag": True}) == {
        "document": "[REDACTED:number]",
        "count": 42,
        "flag": True,
    }


def test_other_values_pass_through_unchanged() -> None:
    marker = object()

    assert redact(marker) is marker
    assert redact(None) is None
    assert redact(1.5) == 1.5


@given(email=st.emails())
def test_no_generated_email_address_survives(email: str) -> None:
    scrubbed = scrub_text(f"contact {email} for details")

    assert email not in scrubbed
    assert "[REDACTED:email]" in scrubbed


@given(text=st.text(max_size=200))
def test_redaction_is_idempotent(text: str) -> None:
    once = scrub_text(text)

    assert scrub_text(once) == once
