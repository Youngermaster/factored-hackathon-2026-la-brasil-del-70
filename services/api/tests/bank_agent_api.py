"""HTTP API test support: settings, identity fixtures, containers, and a client that speaks the CSRF protocol.

Every value is a fixture: team-made, synthetic, and labeled as such. The personas map onto the workflow scenario
customers (``bank_agent_scenarios``); staff personas are an agent and an evaluator.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from bank_agent.adapters.identity.codes import IdentityKeys
from bank_agent.adapters.identity.store import InMemoryChallengeStore, Subject
from bank_agent.adapters.persistence.memory.sessions import InMemorySessionStore
from bank_agent.adapters.persistence.memory.store import InMemoryStore
from bank_agent.adapters.persistence.memory.unit_of_work import InMemoryUnitOfWorkFactory, standalone_audit_log
from bank_agent.adapters.persistence.postgres.seed import IdentityEntry, StaffEntry
from bank_agent.api.app import create_app
from bank_agent.api.config import SecurityConfig
from bank_agent.asgi import api_config_from
from bank_agent.bootstrap.container import Container
from bank_agent.bootstrap.llm import LlmOverrides
from bank_agent.bootstrap.persistence import PersistenceServices
from bank_agent.bootstrap.settings import AppSettings, load_settings
from bank_agent.ports.llm import LLMClient
from bank_agent.testing.clock import FixedClock
from bank_agent_scenarios import AR, CO, MX, NOW, PT, PT2, scenario_data

SESSION_SECRET = "api-test-session-secret-" + "s" * 40
CSRF_SECRET = "api-test-csrf-secret-" + "c" * 40
CUSTOMER_PERSONAS: Mapping[str, str] = {
    "persona-mx": MX,
    "persona-ar": AR,
    "persona-co": CO,
    "persona-pt": PT,
    "persona-pt2": PT2,
}
AGENT_PERSONA, AGENT_ID = "persona-agent", "STF-AGENT-01"
EVALUATOR_PERSONA, EVALUATOR_ID = "persona-evaluator", "STF-EVAL-01"
DOCUMENT_MX, PHONE_MX = "MX1234567", "9876"
HIGH_LIMIT = "100000"


def keys() -> IdentityKeys:
    return IdentityKeys(SESSION_SECRET.encode("utf-8"))


def api_environment(monkeypatch: pytest.MonkeyPatch, *, demo_mode: bool = True, **overrides: str) -> None:
    """Identity and CSRF secrets, demo codes on, and rate limits high enough that only rate tests hit them."""
    values = {
        "SESSION_SECRET": SESSION_SECRET,
        "CSRF_SECRET": CSRF_SECRET,
        "DEMO_MODE": "true" if demo_mode else "false",
        "WORKFLOW_LLM_UNDERSTANDING": "false",
    }
    for rate_class in ("AUTH", "WRITE", "READ"):
        values[f"RATE_LIMIT_{rate_class}_PER_MINUTE"] = HIGH_LIMIT
        values[f"RATE_LIMIT_SESSION_{rate_class}_PER_MINUTE"] = HIGH_LIMIT
    values.update(overrides)
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def memory_persistence() -> PersistenceServices:
    """The in-memory adapters seeded with the scenario customers and the fixture personas."""
    data = scenario_data()
    store = InMemoryStore()
    store.seed(
        customers=data.customers,
        products=data.products,
        transactions=data.transactions,
        cases=data.cases,
        credit_profiles=data.credit_profiles,
    )
    personas = {persona: Subject(customer_id=customer) for persona, customer in CUSTOMER_PERSONAS.items()}
    personas[AGENT_PERSONA] = Subject(staff_id=AGENT_ID, staff_role="agent")
    personas[EVALUATOR_PERSONA] = Subject(staff_id=EVALUATOR_ID, staff_role="evaluator")
    documents = {keys().document_lookup(DOCUMENT_MX): (MX, keys().phone_lookup(MX, PHONE_MX))}
    return PersistenceServices(
        uow_factory=InMemoryUnitOfWorkFactory(store),
        session_store=InMemorySessionStore(),
        audit_log=standalone_audit_log(store),
        challenge_store=InMemoryChallengeStore(personas=personas, documents=documents),
    )


def postgres_identities() -> tuple[list[IdentityEntry], list[StaffEntry]]:
    """The same personas as seed rows (keyed digests only)."""
    identities = [
        IdentityEntry(
            customer_id=customer,
            persona_id=persona,
            document_lookup=keys().document_lookup(DOCUMENT_MX if customer == MX else f"DOC{customer[-6:]}"),
            phone_last4_lookup=keys().phone_lookup(customer, PHONE_MX),
        )
        for persona, customer in CUSTOMER_PERSONAS.items()
    ]
    staff = [
        StaffEntry(staff_id=AGENT_ID, role="agent", persona_id=AGENT_PERSONA, display_name="Fixture agent"),
        StaffEntry(staff_id=EVALUATOR_ID, role="evaluator", persona_id=EVALUATOR_PERSONA, display_name="Evaluator"),
    ]
    return identities, staff


@dataclass
class ApiHarness:
    app: FastAPI
    container: Container
    clock: FixedClock
    settings: AppSettings


def build_api(
    *, clock: FixedClock | None = None, persistence: PersistenceServices | None = None, **container_overrides: Any
) -> ApiHarness:
    settings = load_settings(env_file=None)
    clock = clock or FixedClock(NOW)
    container = Container(settings, clock=clock, persistence=persistence, **container_overrides)
    return ApiHarness(create_app(container, api_config_from(settings)), container, clock, settings)


class ApiClient:
    """An httpx client over the ASGI app that fetches and echoes the CSRF token like the SPA does."""

    def __init__(self, app: FastAPI, *, client_ip: str = "203.0.113.10", https: bool = False) -> None:
        transport = httpx.ASGITransport(app=app, client=(client_ip, 50000))
        base_url = "https://testserver" if https else "http://testserver"
        self.http = httpx.AsyncClient(transport=transport, base_url=base_url)
        self.csrf_token: str | None = None

    async def __aenter__(self) -> ApiClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.http.aclose()

    async def refresh_csrf(self) -> str:
        response = await self.http.get("/v1/auth/csrf")
        assert response.status_code == 200
        self.csrf_token = str(response.json()["csrf_token"])
        return self.csrf_token

    async def post(self, path: str, json: Any = None, *, csrf: bool = True, **kwargs: Any) -> httpx.Response:
        headers = dict(kwargs.pop("headers", {}))
        if csrf:
            headers["X-CSRF-Token"] = self.csrf_token or await self.refresh_csrf()
        return await self.http.post(path, json=json, headers=headers, **kwargs)

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.http.get(path, **kwargs)

    async def login(self, persona: str, language: str | None = None) -> httpx.Response:
        started = await self.post("/v1/auth/start", {"kind": "persona", "persona_id": persona})
        assert started.status_code == 200, started.text
        body = started.json()
        verify: dict[str, Any] = {"challenge_id": body["challenge_id"], "code": body["demo_code"]}
        if language is not None:
            verify["language"] = language
        verified = await self.post("/v1/auth/verify", verify)
        assert verified.status_code == 200, verified.text
        self.csrf_token = str(verified.json()["csrf_token"])
        return verified

    async def step_up(self) -> httpx.Response:
        started = await self.post("/v1/auth/step-up/start")
        assert started.status_code == 200, started.text
        body = started.json()
        verified = await self.post("/v1/auth/step-up/verify", {"challenge_id": body["challenge_id"],
                                                               "code": body["demo_code"]})  # fmt: skip
        assert verified.status_code == 200, verified.text
        self.csrf_token = str(verified.json()["csrf_token"])
        return verified

    async def open_conversation(self) -> str:
        created = await self.post("/v1/conversations")
        assert created.status_code == 201, created.text
        return str(created.json()["conversation_id"])

    async def say(self, conversation_id: str, text: str, turn_id: str | None = None) -> httpx.Response:
        body = {"turn_id": turn_id or str(uuid.uuid4()), "text": text}
        return await self.post(f"/v1/conversations/{conversation_id}/turns", body)


def production_app(harness: ApiHarness) -> FastAPI:
    """The same container behind a production HTTP configuration (``__Host-`` cookies, ``Secure``, HSTS)."""
    config = api_config_from(harness.settings)
    security = SecurityConfig(
        production=True, csrf_secret=CSRF_SECRET.encode(), rate_limits=config.security.rate_limits
    )
    return create_app(harness.container, replace(config, security=security, expose_docs=False))


@dataclass
class ApiBackend:
    """How a test builds its app: the persistence (memory, or None for the configured PostgreSQL)."""

    name: str
    persistence_factory: Callable[[], PersistenceServices | None]
    built: list[ApiHarness] = field(default_factory=list)

    def build(self, *, llm: LLMClient | None = None, clock: FixedClock | None = None, **overrides: Any) -> ApiHarness:
        llm_overrides = LlmOverrides(primary=llm) if llm is not None else None
        harness = build_api(
            clock=clock or FixedClock(NOW),
            persistence=self.persistence_factory(),
            llm_overrides=llm_overrides,
            **overrides,
        )
        self.built.append(harness)
        return harness
