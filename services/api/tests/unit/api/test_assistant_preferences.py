import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from bank_agent.api.app import create_app
from bank_agent.application.identity.sessions import SessionService
from bank_agent.domain.access import AuthLevel, Role
from bank_agent.domain.errors import ConversationNotFoundError, SessionNotFoundError, ToolArgumentError
from bank_agent.domain.identifiers import ConversationId, CustomerId, LineageId, SessionId
from bank_agent.domain.session import Session
from bank_agent_api import ApiClient as BaseApiClient
from bank_agent_scenarios import NOW
from bank_agent_test_support import FakeProvider, api_config


@dataclass(frozen=True)
class Profile:
    customer_id: str
    assistant_name: str
    avatar_key: str
    updated_at: datetime


class PreferencesStub:
    """Small API test double for the not-yet-integrated profile service."""

    def __init__(self) -> None:
        self.conversation_owners = {
            "conv-000001": "CUS-MX-0001",
            "conv-000002": "CUS-MX-0001",
            "conv-000003": "CUS-CO-0001",
        }
        self.profiles: dict[str, Profile] = {}

    async def _owned(self, session: Session, conversation_id: ConversationId) -> str:
        assert session.customer_id is not None
        customer_id = str(session.customer_id)
        if self.conversation_owners.get(conversation_id) != customer_id:
            raise ConversationNotFoundError()
        return customer_id

    async def get_assistant_profile(self, session: Session, conversation_id: ConversationId) -> SimpleNamespace | None:
        customer_id = await self._owned(session, conversation_id)
        profile = self.profiles.get(customer_id)
        return SimpleNamespace(profile=profile) if profile is not None else None

    async def change_assistant_name(
        self, session: Session, conversation_id: ConversationId, name: str
    ) -> SimpleNamespace:
        customer_id = await self._owned(session, conversation_id)
        normalized = name.strip(" ")
        if not normalized or len(normalized) > 40:
            raise ToolArgumentError("assistant name must be 1 to 40 trimmed characters")
        current = self.profiles.get(customer_id)
        profile = Profile(customer_id, normalized, current.avatar_key if current else "avatar_1", NOW)
        self.profiles[customer_id] = profile
        return SimpleNamespace(profile=profile, avatar_path="/private/path/not-returned.png")

    async def mock_assistant_image(self, session: Session, conversation_id: ConversationId) -> SimpleNamespace:
        customer_id = await self._owned(session, conversation_id)
        current = self.profiles.get(customer_id)
        avatar_key = "avatar_2" if current is None or current.avatar_key == "avatar_1" else "avatar_1"
        profile = Profile(customer_id, current.assistant_name if current else "Assistant", avatar_key, NOW)
        self.profiles[customer_id] = profile
        return SimpleNamespace(profile=profile, avatar_path="/private/path/not-returned.png")


class SessionStoreStub:
    def __init__(self) -> None:
        self.sessions = {
            "token-mx": _session("CUS-MX-0001", "ses-mx"),
            "token-co": _session("CUS-CO-0001", "ses-co"),
        }

    async def resolve(self, token: str) -> Session:
        if token not in self.sessions:
            raise SessionNotFoundError()
        return self.sessions[token]


def _session(customer_id: str, session_id: str) -> Session:
    return Session(
        session_id=SessionId(session_id),
        lineage_id=LineageId(f"lin-{session_id}"),
        role=Role.CUSTOMER,
        customer_id=CustomerId(customer_id),
        auth_level=AuthLevel.OTP_VERIFIED,
        created_at=NOW,
        last_seen_at=NOW,
        idle_timeout=timedelta(hours=1),
        absolute_expires_at=NOW + timedelta(days=1),
    )


class PreferencesProvider(FakeProvider):
    def __init__(self) -> None:
        super().__init__()
        self._sessions = SessionStoreStub()
        self.assistant_preferences = PreferencesStub()

    @property
    def session_service(self) -> SessionService:
        return self._sessions  # type: ignore[return-value]


class ApiClient(BaseApiClient):
    """Keep in-process requests bounded when a test dependency stalls."""

    async def refresh_csrf(self) -> str:
        return await asyncio.wait_for(super().refresh_csrf(), timeout=5)

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return await asyncio.wait_for(super().get(path, **kwargs), timeout=5)

    async def post(self, path: str, json: Any = None, **kwargs: Any) -> httpx.Response:
        return await asyncio.wait_for(super().post(path, json, **kwargs), timeout=5)


@pytest.fixture(autouse=True)
def inline_pure_sync_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    """This sandbox cannot complete worker-thread futures; these FastAPI dependencies are pure and cheap."""

    async def run_inline(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    monkeypatch.setattr("fastapi.dependencies.utils.run_in_threadpool", run_inline)


@pytest.fixture
def api() -> tuple[PreferencesProvider, FastAPI]:
    provider = PreferencesProvider()
    app = create_app(provider, api_config())
    return provider, app


def _authenticated(client: BaseApiClient, token: str) -> None:
    client.http.cookies.set("session", token)


@pytest.mark.unit
async def test_name_and_predefined_image_changes_return_saved_customer_profile(
    api: tuple[PreferencesProvider, FastAPI],
) -> None:
    _, app = api
    async with ApiClient(app) as client:
        _authenticated(client, "token-mx")
        await client.refresh_csrf()
        conversation_id = "conv-000001"

        initial = await client.get(f"/v1/conversations/{conversation_id}/assistant-profile")
        assert initial.status_code == 200
        assert initial.json()["assistant_name"] == "Assistant"
        assert initial.json()["avatar_key"] == "avatar_1"

        named = await client.post(f"/v1/conversations/{conversation_id}/assistant-profile/name", {"name": "  Camila  "})
        assert named.status_code == 200
        assert named.json()["assistant_name"] == "Camila"
        assert named.json()["avatar_url"] == "/v1/assistant-profile/avatars/avatar_1.png"
        assert "private" not in named.text

        image = await client.post(f"/v1/conversations/{conversation_id}/assistant-profile/mock-image")
        assert image.status_code == 200
        assert image.json()["assistant_name"] == "Camila"
        assert image.json()["avatar_key"] == "avatar_2"


@pytest.mark.unit
@pytest.mark.parametrize("name", ["", "   ", "x" * 41])
async def test_invalid_assistant_names_use_problem_details(api: tuple[PreferencesProvider, FastAPI], name: str) -> None:
    _, app = api
    async with ApiClient(app) as client:
        _authenticated(client, "token-mx")
        await client.refresh_csrf()
        conversation_id = "conv-000001"

        response = await client.post(f"/v1/conversations/{conversation_id}/assistant-profile/name", {"name": name})

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")


@pytest.mark.unit
async def test_profile_routes_require_a_verified_customer_session(api: tuple[PreferencesProvider, FastAPI]) -> None:
    _, app = api
    async with ApiClient(app) as client:
        await client.refresh_csrf()
        read = await client.get("/v1/conversations/conv-000001/assistant-profile")
        write = await client.post("/v1/conversations/conv-000001/assistant-profile/name", {"name": "Camila"})

    assert read.status_code == 401
    assert write.status_code == 401


@pytest.mark.unit
async def test_profile_is_customer_wide_but_conversations_remain_session_scoped(
    api: tuple[PreferencesProvider, FastAPI],
) -> None:
    _, app = api
    async with ApiClient(app) as customer, ApiClient(app) as another_customer:
        _authenticated(customer, "token-mx")
        await customer.refresh_csrf()
        first_chat = "conv-000001"
        changed = await customer.post(f"/v1/conversations/{first_chat}/assistant-profile/name", {"name": "Camila"})
        assert changed.status_code == 200

        second_chat = "conv-000002"
        restored = await customer.get(f"/v1/conversations/{second_chat}/assistant-profile")
        assert restored.status_code == 200
        assert restored.json()["assistant_name"] == "Camila"

        _authenticated(another_customer, "token-co")
        await another_customer.refresh_csrf()
        foreign = await another_customer.get(f"/v1/conversations/{first_chat}/assistant-profile")

    assert foreign.status_code == 404
