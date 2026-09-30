"""Smoke test of a deployed stack, standard library only (deploy/smoke_test.sh is the entry point).

Checks, in order: the TLS certificate (valid for the host, days left), the health endpoints, the security headers of
the SPA and of the API, the demo sign-in and its cookies, one conversation per workflow across both languages
(account inquiry in es, card support in pt, a dispute intake in es and in pt that stops at its clarifying question, and
credit in pt), an out-of-scope request answered with an abstention, and a cross-customer probe answered with 404.
Every conversation is read only, so the smoke test can run daily against the public demo without changing its data.
It prints what it checks, never a code, a cookie value, or a token, and exits 1 on the first failure.
"""

import argparse
import http.cookiejar
import json
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

MIN_CERT_DAYS = 7
MAX_RATE_LIMIT_WAIT = 75


class SmokeCheckError(Exception):
    pass


@dataclass(frozen=True)
class Flow:
    name: str
    persona: str
    text: str
    workflow: str | None
    outcomes: frozenset[str]


FLOWS = (
    Flow("account inquiry (es)", "acc-mx-accounts", "¿Cuál es el saldo de mis cuentas?", "account_inquiry",
         frozenset({"resolved", "clarified"})),
    Flow("card support (pt)", "crd-co-declined", "Qual é o status do meu cartão?", "card_support",
         frozenset({"resolved", "clarified"})),
    Flow("dispute intake (es)", "dsp-co-unrecognized", "No reconozco un cargo en mi tarjeta de crédito", "dispute",
         frozenset({"clarified", "in_progress"})),
    Flow("dispute intake (pt)", "dsp-co-unrecognized", "Não reconheço uma cobrança no meu cartão de crédito", "dispute",
         frozenset({"clarified", "in_progress"})),
    Flow("credit catalog (pt)", "cre-mx-complete", "Quais cartões de crédito vocês têm?", "credit",
         frozenset({"resolved", "clarified"})),
    Flow("out of scope (es)", "cre-mx-complete", "¿En qué acciones de la bolsa me recomiendas invertir mis ahorros?",
         None, frozenset({"abstained"})),
)  # fmt: skip
SPA_HEADERS = {
    "content-security-policy": ("default-src 'none'", "script-src 'self'", "frame-ancestors 'none'"),
    "strict-transport-security": ("max-age=",),
    "x-content-type-options": ("nosniff",),
    "referrer-policy": ("no-referrer",),
    "permissions-policy": ("camera=()",),
}
API_HEADERS = {
    "content-security-policy": ("default-src 'none'", "frame-ancestors 'none'"),
    "strict-transport-security": ("max-age=",),
    "x-content-type-options": ("nosniff",),
    "cache-control": ("no-store",),
}


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeCheckError(message)
    print(f"ok    {message}")


def certificate(base: str, context: ssl.SSLContext, min_days: int) -> None:
    parts = urlsplit(base)
    host, port = parts.hostname or "", parts.port or 443
    with (
        socket.create_connection((host, port), timeout=10) as raw,
        context.wrap_socket(raw, server_hostname=host) as tls,
    ):
        cert: dict[str, Any] = dict(tls.getpeercert() or {})
    expires = datetime.fromtimestamp(ssl.cert_time_to_seconds(str(cert.get("notAfter"))), UTC)
    days = (expires - datetime.now(UTC)).days
    issuer = {str(name): str(value) for entry in cert.get("issuer", ()) for name, value in entry}
    name = issuer.get("organizationName", issuer.get("commonName", "unknown"))
    check(days >= min_days, f"TLS certificate valid for {host}, {days} days left, issuer {name}")


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    cookies: list[str]
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body or b"null")


class Client:
    """A cookie-keeping HTTPS client that echoes the CSRF token like the SPA and waits out rate limits."""

    def __init__(self, base: str, context: ssl.SSLContext) -> None:
        self.base = base.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=context), urllib.request.HTTPCookieProcessor(self.jar)
        )
        self.csrf: str | None = None

    def request(self, method: str, path: str, body: Any = None) -> Response:
        headers = {"Accept": "application/json", "User-Agent": "bank-agent-smoke/1"}
        data = None
        if body is not None or method == "POST":
            data = json.dumps(body if body is not None else {}).encode()
            headers["Content-Type"] = "application/json"
        if method == "POST":
            headers["X-CSRF-Token"] = self.csrf or self.refresh_csrf()
        for _ in range(3):
            # The base URL is checked to be https in main(); no other scheme reaches here.
            request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)  # noqa: S310  # nosec B310
            try:
                with self.opener.open(request, timeout=90) as raw:
                    return Response(raw.status, {k.lower(): v for k, v in raw.headers.items()},
                                    raw.headers.get_all("Set-Cookie") or [], raw.read())  # fmt: skip
            except urllib.error.HTTPError as error:
                if error.code == 429:
                    wait = min(int(error.headers.get("Retry-After", "5")), MAX_RATE_LIMIT_WAIT)
                    print(f"wait  rate limited on {path}, retrying in {wait} s")
                    time.sleep(wait)
                    continue
                return Response(error.code, {k.lower(): v for k, v in error.headers.items()},
                                error.headers.get_all("Set-Cookie") or [], error.read())  # fmt: skip
        raise SmokeCheckError(f"{path} stayed rate limited")

    def refresh_csrf(self) -> str:
        response = self.request("GET", "/v1/auth/csrf")
        check(response.status == 200, "GET /v1/auth/csrf answers 200")
        self.csrf = str(response.json()["csrf_token"])
        return self.csrf

    def login(self, persona: str) -> Response:
        started = self.request("POST", "/v1/auth/start", {"kind": "persona", "persona_id": persona})
        check(started.status == 200, f"demo sign-in starts for {persona}")
        code = started.json().get("demo_code")
        check(bool(code), "the demo code is returned (DEMO_MODE with ALLOW_PUBLIC_DEMO_MODE)")
        challenge = {"challenge_id": started.json()["challenge_id"], "code": code}
        verified = self.request("POST", "/v1/auth/verify", challenge)
        check(verified.status == 200, f"demo sign-in completes for {persona}")
        self.csrf = str(verified.json()["csrf_token"])
        return verified

    def conversation(self) -> str:
        created = self.request("POST", "/v1/conversations")
        check(created.status == 201, "a conversation opens")
        return str(created.json()["conversation_id"])

    def say(self, conversation: str, text: str) -> Response:
        turn = {"turn_id": str(uuid.uuid4()), "text": text}
        return self.request("POST", f"/v1/conversations/{conversation}/turns", turn)


def headers_present(response: Response, expected: dict[str, tuple[str, ...]], where: str) -> None:
    for name, fragments in expected.items():
        value = response.headers.get(name, "")
        check(all(fragment in value for fragment in fragments), f"{where}: {name} is set")


def cookie_flags(cookies: list[str]) -> None:
    session = [cookie for cookie in cookies if cookie.startswith("__Host-session=")]
    check(len(session) == 1, "the session cookie uses the __Host- prefix")
    flags = {part.strip().lower() for part in session[0].split(";")[1:]}
    expected = {"secure", "httponly", "samesite=strict", "path=/"}
    check(expected <= flags, "the session cookie is Secure, HttpOnly, SameSite=Strict, Path=/")
    check(not any(flag.startswith("domain=") for flag in flags), "the session cookie has no Domain attribute")
    csrf = [cookie for cookie in cookies if cookie.startswith("__Host-csrf=")]
    check(len(csrf) == 1 and "secure" in csrf[0].lower(), "the CSRF cookie uses the __Host- prefix and Secure")


def run(base: str, context: ssl.SSLContext, min_cert_days: int = MIN_CERT_DAYS) -> None:
    certificate(base, context, min_cert_days)
    client = Client(base, context)
    for path in ("/health/live", "/health/ready"):
        check(client.request("GET", path).status == 200, f"GET {path} answers 200")
    spa = client.request("GET", "/")
    check(spa.status == 200 and b'<div id="root">' in spa.body, "the SPA is served")
    headers_present(spa, SPA_HEADERS, "SPA")
    check(b"<script>" not in spa.body, "the SPA has no inline script")
    headers_present(client.request("GET", "/v1/auth/csrf"), API_HEADERS, "API")
    client.csrf = None
    cookie_flags(client.login(FLOWS[0].persona).cookies)
    signed_in = FLOWS[0].persona
    first_conversation = ""
    for flow in FLOWS:
        if flow.persona != signed_in:
            client.login(flow.persona)
            signed_in = flow.persona
        conversation = client.conversation()
        first_conversation = first_conversation or conversation
        reply = client.say(conversation, flow.text)
        check(reply.status == 200, f"{flow.name}: the turn answers 200")
        body = reply.json()
        workflow = (body.get("workflow") or {}).get("id")
        if flow.workflow is not None:
            check(workflow == flow.workflow, f"{flow.name}: routed to {flow.workflow}")
        outcome = body["outcome"]
        check(outcome in flow.outcomes, f"{flow.name}: outcome {outcome} is one of {sorted(flow.outcomes)}")
        check(bool(body["message"].get("text")), f"{flow.name}: the assistant replied")
    probe = client.request("GET", f"/v1/conversations/{first_conversation}")
    check(probe.status == 404, f"{signed_in} reading another customer's conversation gets 404 (cross-customer probe)")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", help="for example https://demo.example.org")
    parser.add_argument("--ca-file", help="a CA certificate to trust (the local TLS mode's Caddy root)")
    parser.add_argument(
        "--min-cert-days",
        type=int,
        default=MIN_CERT_DAYS,
        help="fail when the certificate expires sooner (0 for Caddy's short-lived local certificates)",
    )
    arguments = parser.parse_args(argv)
    if not arguments.base_url.startswith("https://"):
        print("fail  the base URL must be https", file=sys.stderr)
        return 2
    context = ssl.create_default_context(cafile=arguments.ca_file)
    try:
        run(arguments.base_url, context, arguments.min_cert_days)
    except (SmokeCheckError, OSError, KeyError, ValueError) as error:
        print(f"fail  {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print("smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
