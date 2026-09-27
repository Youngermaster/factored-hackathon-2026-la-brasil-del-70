"""One-time codes and keyed digests.

Codes are six digits from ``secrets``. A stored code is ``HMAC-SHA256(otp_key, salt | challenge_id | code)``
with a 16-byte random salt per challenge, so a leaked table cannot be brute-forced without the server secret, and
comparison is constant time. Purpose-specific keys are derived from the one server secret (``SESSION_SECRET``)
with HMAC and fixed labels, so no key is reused for two purposes.
"""

import hashlib
import hmac
import secrets
import unicodedata

CODE_DIGITS = 6
_OTP_LABEL = b"bank-agent/otp-code/v1"
_LOOKUP_LABEL = b"bank-agent/identity-lookup/v1"
MIN_SECRET_BYTES = 32


def generate_code() -> str:
    return f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"


def new_salt() -> str:
    return secrets.token_hex(16)


def _hmac_hex(key: bytes, message: str) -> str:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).hexdigest()


def normalize_document(document_number: str) -> str:
    """Upper case, without separators or spaces, so ``ab-123`` and ``AB123`` match."""
    folded = unicodedata.normalize("NFKC", document_number).upper()
    return "".join(character for character in folded if character.isalnum())


class IdentityKeys:
    """The derived keys. Never logs, stores, or returns the secret."""

    def __init__(self, secret: bytes) -> None:
        if len(secret) < MIN_SECRET_BYTES:
            raise ValueError(f"the identity secret needs at least {MIN_SECRET_BYTES} bytes")
        self._otp_key = hmac.new(secret, _OTP_LABEL, hashlib.sha256).digest()
        self._lookup_key = hmac.new(secret, _LOOKUP_LABEL, hashlib.sha256).digest()

    def __repr__(self) -> str:
        return "IdentityKeys(<redacted>)"

    def code_hash(self, *, salt: str, challenge_id: str, code: str) -> str:
        return _hmac_hex(self._otp_key, f"{salt}|{challenge_id}|{code}")

    def code_matches(self, *, expected_hash: str, salt: str, challenge_id: str, code: str) -> bool:
        """Constant-time comparison of the stored hash with the hash of ``code``."""
        candidate = self.code_hash(salt=salt, challenge_id=challenge_id, code=code)
        return hmac.compare_digest(candidate, expected_hash)

    def document_lookup(self, document_number: str) -> str:
        return _hmac_hex(self._lookup_key, f"document|{normalize_document(document_number)}")

    def phone_lookup(self, customer_id: str, phone_last4: str) -> str:
        return _hmac_hex(self._lookup_key, f"phone|{customer_id}|{phone_last4}")

    def phone_matches(self, customer_id: str, phone_last4: str, expected_lookup: str) -> bool:
        return hmac.compare_digest(self.phone_lookup(customer_id, phone_last4), expected_lookup)

    def subject_key(self, kind: str, value: str) -> str:
        """The lockout key of an identification (persona id, document, or session subject)."""
        return _hmac_hex(self._lookup_key, f"subject|{kind}|{value}")
