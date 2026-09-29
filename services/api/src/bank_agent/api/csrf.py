"""Signed double-submit CSRF tokens (ADR 0031).

``GET /v1/auth/csrf`` sets a readable cookie with a token; every state-changing request echoes it in
``X-CSRF-Token``. A token is ``<nonce>.<signature>``: the signature is HMAC-SHA256 over the binding and the nonce,
keyed by ``CSRF_SECRET``. The binding is the SHA-256 of the session token, or ``anonymous`` before login, so a token
planted in a cookie by another site or subdomain is useless for a different session. Tokens rotate on login and
step-up (the session token changes) and on logout (back to anonymous).
"""

import base64
import hashlib
import hmac
import secrets
from typing import Final

CSRF_HEADER: Final = "X-CSRF-Token"
ANONYMOUS_BINDING: Final = "anonymous"
_NONCE_BYTES: Final = 16
MAX_TOKEN_LENGTH: Final = 128
_LABEL: Final = b"bank-agent/csrf/v1"


def binding_for(session_token: str | None) -> str:
    """The binding of a token: the session token's digest, or ``anonymous`` without a session."""
    if not session_token:
        return ANONYMOUS_BINDING
    return hashlib.sha256(session_token.encode("utf-8")).hexdigest()


class CsrfTokens:
    """Issues and checks tokens with one secret."""

    def __init__(self, secret: bytes) -> None:
        self._key = hmac.new(secret, _LABEL, hashlib.sha256).digest()

    def _signature(self, binding: str, nonce: str) -> str:
        message = f"{binding}\n{nonce}".encode()
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()

    def issue(self, binding: str) -> str:
        nonce = base64.urlsafe_b64encode(secrets.token_bytes(_NONCE_BYTES)).rstrip(b"=").decode("ascii")
        return f"{nonce}.{self._signature(binding, nonce)}"

    def is_valid(self, token: str, binding: str) -> bool:
        """True when ``token`` is well formed and signed for ``binding``. Constant time in the signature."""
        if len(token) > MAX_TOKEN_LENGTH:
            return False
        nonce, separator, signature = token.partition(".")
        if not separator or not nonce or not signature:
            return False
        return hmac.compare_digest(signature, self._signature(binding, nonce))

    def accepts(self, *, header: str | None, cookie: str | None, session_token: str | None) -> bool:
        """The double-submit check: the header equals the cookie and is signed for the current session."""
        if not header or not cookie or len(header) > MAX_TOKEN_LENGTH or len(cookie) > MAX_TOKEN_LENGTH:
            return False
        if not hmac.compare_digest(header.encode("utf-8"), cookie.encode("utf-8")):
            return False
        return self.is_valid(header, binding_for(session_token))
