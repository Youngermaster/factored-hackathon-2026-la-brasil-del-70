import hmac
import re
from unittest.mock import patch

import pytest

from bank_agent.adapters.identity.codes import IdentityKeys, generate_code, new_salt, normalize_document
from bank_agent.adapters.identity.sender import DemoOtpSender
from bank_agent.domain.identifiers import ChallengeId, CustomerId
from bank_agent.domain.identity import OtpDispatch, OtpPurpose
from bank_agent_builders import T0

SECRET = b"fixture-secret-" + b"x" * 32


def test_codes_are_six_digits() -> None:
    for _ in range(50):
        assert re.fullmatch(r"[0-9]{6}", generate_code())


def test_codes_keep_leading_zeros() -> None:
    with patch("secrets.randbelow", return_value=42):
        assert generate_code() == "000042"


def test_salts_are_sixteen_random_bytes() -> None:
    first, second = new_salt(), new_salt()
    assert re.fullmatch(r"[0-9a-f]{32}", first)
    assert first != second


def test_code_hash_depends_on_salt_challenge_and_code() -> None:
    keys = IdentityKeys(SECRET)
    base = keys.code_hash(salt="aa", challenge_id="chl-1", code="123456")
    assert base != keys.code_hash(salt="bb", challenge_id="chl-1", code="123456")
    assert base != keys.code_hash(salt="aa", challenge_id="chl-2", code="123456")
    assert base != keys.code_hash(salt="aa", challenge_id="chl-1", code="123457")
    assert base != IdentityKeys(b"another-" + SECRET).code_hash(salt="aa", challenge_id="chl-1", code="123456")


def test_code_comparison_is_constant_time() -> None:
    keys = IdentityKeys(SECRET)
    stored = keys.code_hash(salt="aa", challenge_id="chl-1", code="123456")
    with patch("hmac.compare_digest", wraps=hmac.compare_digest) as compare:
        assert keys.code_matches(expected_hash=stored, salt="aa", challenge_id="chl-1", code="123456")
        assert not keys.code_matches(expected_hash=stored, salt="aa", challenge_id="chl-1", code="000000")
    assert compare.call_count == 2


def test_lookups_normalize_documents_and_bind_the_phone_to_the_customer() -> None:
    keys = IdentityKeys(SECRET)
    assert normalize_document(" ab-12.34 ") == "AB1234"
    assert keys.document_lookup("ab-1234") == keys.document_lookup("AB1234")
    phone = keys.phone_lookup("C1", "4321")
    assert keys.phone_matches("C1", "4321", phone)
    assert not keys.phone_matches("C2", "4321", phone)
    assert not keys.phone_matches("C1", "4322", phone)


def test_short_secrets_are_refused_and_never_shown() -> None:
    with pytest.raises(ValueError, match="at least 32 bytes"):
        IdentityKeys(b"short")
    assert "fixture" not in repr(IdentityKeys(SECRET))


def _dispatch() -> OtpDispatch:
    return OtpDispatch(
        challenge_id=ChallengeId("chl-000001"),
        purpose=OtpPurpose.LOGIN,
        recipient_customer_id=CustomerId("CUS-A-0001"),
        code="123456",
        expires_at=T0,
    )


async def test_demo_sender_returns_the_code_only_in_demo_mode() -> None:
    events: list[tuple[str, dict[str, str]]] = []
    demo = await DemoOtpSender(demo_mode=True, emit=lambda name, fields: events.append((name, dict(fields)))).send(
        _dispatch()
    )
    real = await DemoOtpSender(demo_mode=False, emit=lambda name, fields: events.append((name, dict(fields)))).send(
        _dispatch()
    )
    assert (demo.channel, demo.demo_code) == ("demo", "123456")
    assert (real.channel, real.demo_code) == ("sms", None)
    assert all("123456" not in str(fields) for _, fields in events)
    assert [name for name, _ in events] == ["otp_delivery_requested", "otp_delivery_requested"]


def test_decoy_receipts_look_like_real_ones() -> None:
    sender = DemoOtpSender(demo_mode=False, emit=lambda name, fields: None)
    assert sender.decoy_receipt("chl-000002", "654321").model_dump() == {
        "delivered": True,
        "channel": "sms",
        "demo_code": None,
    }
