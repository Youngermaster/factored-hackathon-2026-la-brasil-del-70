from datetime import UTC, datetime
from pathlib import Path

import pytest

from bank_agent.adapters.persistence.memory.store import InMemoryStore
from bank_agent.adapters.persistence.memory.unit_of_work import InMemoryUnitOfWorkFactory
from bank_agent.application.preferences.service import AssistantPreferencesService
from bank_agent.domain.errors import ConversationNotFoundError, ToolArgumentError
from bank_agent.domain.identifiers import ConversationId
from bank_agent.testing.clock import FixedClock
from bank_agent_builders import CUSTOMER_A, CUSTOMER_B, conversation, session

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


def service(store: InMemoryStore) -> AssistantPreferencesService:
    return AssistantPreferencesService(InMemoryUnitOfWorkFactory(store), FixedClock(NOW))


def is_file(path: str) -> bool:
    return Path(path).is_file()


@pytest.mark.asyncio
async def test_name_is_customer_wide_and_preserves_existing_avatar() -> None:
    store = InMemoryStore()
    store.seed(conversations=[conversation("conv-a1"), conversation("conv-a2")])
    preferences = service(store)

    changed = await preferences.change_assistant_name(session(), ConversationId("conv-a1"), "  Camila  ")
    assert changed.profile.assistant_name == "Camila"
    assert changed.profile.avatar_key == "avatar_1"

    image = await preferences.mock_assistant_image(session(), ConversationId("conv-a2"))
    assert image.profile.assistant_name == "Camila"
    assert image.profile.customer_id == CUSTOMER_A
    assert image.avatar_path.endswith(f"{image.profile.avatar_key}.png")
    assert is_file(image.avatar_path)


@pytest.mark.asyncio
async def test_mock_avatar_creates_profile_and_later_name_change_preserves_it(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryStore()
    store.seed(conversations=[conversation("conv-a1")])
    monkeypatch.setattr("bank_agent.application.preferences.service.secrets.choice", lambda choices: "avatar_2")
    preferences = service(store)

    image = await preferences.mock_assistant_image(session(), ConversationId("conv-a1"))
    assert image.profile.assistant_name == "Assistant"
    assert image.profile.avatar_key == "avatar_2"
    assert is_file(image.avatar_path)

    changed = await preferences.change_assistant_name(session(), ConversationId("conv-a1"), "Rafa")
    assert changed.profile.avatar_key == "avatar_2"
    assert changed.profile.assistant_name == "Rafa"


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["", "   ", "x" * 41])
async def test_name_matches_database_length_and_trim_constraints(name: str) -> None:
    store = InMemoryStore()
    store.seed(conversations=[conversation("conv-a1")])

    with pytest.raises(ToolArgumentError):
        await service(store).change_assistant_name(session(), ConversationId("conv-a1"), name)


@pytest.mark.asyncio
async def test_name_accepts_exact_database_limit() -> None:
    store = InMemoryStore()
    store.seed(conversations=[conversation("conv-a1")])

    changed = await service(store).change_assistant_name(session(), ConversationId("conv-a1"), "x" * 40)

    assert changed.profile.assistant_name == "x" * 40


@pytest.mark.asyncio
async def test_foreign_conversation_is_rejected_without_mutating_either_profile() -> None:
    store = InMemoryStore()
    store.seed(conversations=[conversation("conv-b1", customer_id=CUSTOMER_B)])

    with pytest.raises(ConversationNotFoundError):
        await service(store).change_assistant_name(session(), ConversationId("conv-b1"), "Camila")
    with pytest.raises(ConversationNotFoundError):
        await service(store).mock_assistant_image(session(), ConversationId("conv-b1"))

    assert store.assistant_profiles == {}
