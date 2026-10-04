"""The deploy smoke test's own behavior: how it reacts to 429s, and how many conversations each persona opens.

The smoke test runs against the same seeded personas on every deploy, and new conversations count against each
customer's new-chat quota (ADR 0026). These tests drive ``deploy/smoke_test.py`` with fake transports; no network.
"""

import email.message
import importlib.util
import io
import json
import ssl
import sys
import urllib.error
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

DEPLOY = Path(__file__).resolve().parents[4] / "deploy"
CREATION_LIMITED = {"type": "https://bank-agent.local/problems/conversation-creation-limited", "status": 429}
RATE_LIMITED = {"type": "https://bank-agent.local/problems/rate-limited", "status": 429}


def _load_smoke() -> ModuleType:
    spec = importlib.util.spec_from_file_location("deploy_smoke_test", DEPLOY / "smoke_test.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SMOKE = _load_smoke()


def _too_many(problem: dict[str, Any], retry_after: str) -> urllib.error.HTTPError:
    headers = email.message.Message()
    headers["Retry-After"] = retry_after
    headers["Content-Type"] = "application/problem+json"
    body = io.BytesIO(json.dumps(problem).encode())
    return urllib.error.HTTPError("https://demo.example/v1/conversations", 429, "Too Many Requests", headers, body)


class _RefusingOpener:
    """Answers every request with the next prepared HTTP error."""

    def __init__(self, errors: list[urllib.error.HTTPError]) -> None:
        self.errors = errors
        self.calls = 0

    def open(self, request: object, timeout: float) -> object:
        self.calls += 1
        raise self.errors.pop(0)


def _client(errors: list[urllib.error.HTTPError]) -> tuple[Any, _RefusingOpener]:
    client = SMOKE.Client("https://demo.example", ssl.create_default_context())
    client.csrf = "fixture-csrf-token"
    client.persona = "cre-mx-complete"
    opener = _RefusingOpener(errors)
    client.opener = opener
    return client, opener


@pytest.mark.parametrize(
    "problem", [CREATION_LIMITED, {"type": "about:blank", "code": "conversation_creation_limited", "status": 429}]
)
def test_an_exhausted_creation_quota_is_reported_by_name_without_waiting(
    monkeypatch: pytest.MonkeyPatch, problem: dict[str, Any]
) -> None:
    monkeypatch.setattr(SMOKE.time, "sleep", lambda seconds: pytest.fail(f"waited {seconds} s"))
    client, opener = _client([_too_many(problem, "1800")])
    with pytest.raises(SMOKE.SmokeCheckError) as raised:
        client.request("POST", "/v1/conversations")
    message = str(raised.value)
    assert "conversation_creation_limited" in message
    assert "cre-mx-complete" in message
    assert "Retry-After 1800 s" in message
    assert "CONVERSATION_CREATION_LIMIT" in message
    assert "stayed rate limited" not in message
    assert opener.calls == 1


def test_a_request_rate_limit_is_still_waited_out_then_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    waits: list[float] = []
    monkeypatch.setattr(SMOKE.time, "sleep", waits.append)
    client, opener = _client([_too_many(RATE_LIMITED, "500") for _ in range(3)])
    with pytest.raises(SMOKE.SmokeCheckError, match="/v1/conversations stayed rate limited"):
        client.request("POST", "/v1/conversations")
    assert waits == [SMOKE.MAX_RATE_LIMIT_WAIT] * 3
    assert opener.calls == 3


@pytest.mark.parametrize("body", [b"", b"not json", b"[]", json.dumps(RATE_LIMITED).encode()])
def test_other_429_bodies_are_not_mistaken_for_the_creation_quota(body: bytes) -> None:
    assert SMOKE.creation_limited(body) is False


def _headers(expected: dict[str, tuple[str, ...]]) -> dict[str, str]:
    return {name: "; ".join(fragments) for name, fragments in expected.items()}


class _FakeStack:
    """A deployed stack as the smoke test sees it, recording which persona opens which conversation."""

    def __init__(self, base: str, context: ssl.SSLContext) -> None:
        self.persona = ""
        self.opened: list[tuple[str, str]] = []
        self.turns: list[tuple[str, str]] = []
        _FakeStack.last = self

    last: "_FakeStack"

    def request(self, method: str, path: str, body: Any = None) -> Any:
        if path in ("/health/live", "/health/ready"):
            return SMOKE.Response(200, {}, [], b"")
        if path == "/":
            return SMOKE.Response(200, _headers(SMOKE.SPA_HEADERS), [], b'<div id="root"></div>')
        if path == "/v1/auth/csrf":
            return SMOKE.Response(200, _headers(SMOKE.API_HEADERS), [], b'{"csrf_token": "fixture"}')
        owner = {conversation: persona for persona, conversation in self.opened}[path.rsplit("/", 1)[1]]
        return SMOKE.Response(404 if owner != self.persona else 200, {}, [], b"{}")

    def login(self, persona: str) -> Any:
        self.persona = persona
        cookies = ["__Host-session=fixture; Path=/; Secure; HttpOnly; SameSite=Strict", "__Host-csrf=fixture; Secure"]
        return SMOKE.Response(200, {}, cookies, b"{}")

    def conversation(self) -> str:
        conversation = f"conv-fixture-{len(self.opened)}"
        self.opened.append((self.persona, conversation))
        return conversation

    def say(self, conversation: str, text: str) -> Any:
        self.turns.append((conversation, text))
        (flow,) = [flow for flow in SMOKE.FLOWS if flow.text == text]
        reply = {"workflow": {"id": flow.workflow}, "outcome": min(flow.outcomes), "message": {"text": "fixture"}}
        return SMOKE.Response(200, {}, [], json.dumps(reply).encode())


def test_each_persona_opens_only_the_conversations_its_checks_need(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SMOKE, "certificate", lambda base, context, min_days: None)
    monkeypatch.setattr(SMOKE, "Client", _FakeStack)
    SMOKE.run("https://demo.example", ssl.create_default_context())
    stack = _FakeStack.last
    opens = Counter(persona for persona, _ in stack.opened)
    assert opens == {
        "acc-mx-accounts": 1,
        "crd-co-declined": 1,
        "dsp-co-unrecognized": 2,
        "dsp-mx-open-case": 1,
        "cre-mx-complete": 1,
    }
    conversation_of = dict(stack.turns)
    by_text = {text: conversation for conversation, text in stack.turns}
    (credit,) = [flow for flow in SMOKE.FLOWS if flow.workflow == "credit"]
    (out_of_scope,) = [flow for flow in SMOKE.FLOWS if flow.workflow is None]
    assert by_text[out_of_scope.text] == by_text[credit.text]
    assert len(conversation_of) == len(stack.opened) == len(SMOKE.FLOWS) - 1
