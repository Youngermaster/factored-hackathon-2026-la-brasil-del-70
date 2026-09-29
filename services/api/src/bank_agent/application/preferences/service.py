"""Use cases for changing the customer-wide assistant name and mock avatar."""

import secrets
from dataclasses import dataclass
from importlib.resources import files

from bank_agent.domain.access import Role
from bank_agent.domain.assistant_profile import AssistantProfile
from bank_agent.domain.errors import AccessContextError, ConversationNotFoundError, ToolArgumentError
from bank_agent.domain.identifiers import ConversationId
from bank_agent.domain.session import Session
from bank_agent.ports.determinism import Clock
from bank_agent.ports.unit_of_work import UnitOfWorkFactory

DEFAULT_ASSISTANT_NAME = "Assistant"
AVATAR_KEYS = ("avatar_1", "avatar_2")


@dataclass(frozen=True, slots=True)
class AssistantPreference:
    profile: AssistantProfile
    avatar_path: str


def _customer_only(session: Session) -> None:
    if session.role is not Role.CUSTOMER:
        raise AccessContextError("assistant preferences belong to customer sessions")


def _avatar_path(key: str) -> str:
    if key not in AVATAR_KEYS:
        raise ValueError("unknown local avatar key")
    return str(files("bank_agent").joinpath("assets", "avatars", f"{key}.png"))


class AssistantPreferencesService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory, self._clock = uow_factory, clock

    async def change_assistant_name(
        self, session: Session, conversation_id: ConversationId, name: str
    ) -> AssistantPreference:
        _customer_only(session)
        # PostgreSQL btrim(text) removes ordinary spaces by default; match that exact rule here.
        normalized = name.strip(" ")
        if not normalized or len(normalized) > 40:
            raise ToolArgumentError("assistant name must be 1 to 40 trimmed characters")
        async with self._uow_factory(session.access_context()) as uow:
            if await uow.conversations.get(conversation_id) is None:
                raise ConversationNotFoundError()
            profile = await uow.assistant_profiles.set_name(normalized, now=self._clock.now())
            await uow.commit()
        return AssistantPreference(profile, _avatar_path(profile.avatar_key))

    async def mock_assistant_image(self, session: Session, conversation_id: ConversationId) -> AssistantPreference:
        _customer_only(session)
        async with self._uow_factory(session.access_context()) as uow:
            if await uow.conversations.get(conversation_id) is None:
                raise ConversationNotFoundError()
            profile = await uow.assistant_profiles.set_avatar(secrets.choice(AVATAR_KEYS), now=self._clock.now())
            await uow.commit()
        return AssistantPreference(profile, _avatar_path(profile.avatar_key))
