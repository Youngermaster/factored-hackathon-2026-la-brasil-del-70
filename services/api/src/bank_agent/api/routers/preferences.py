"""Customer-scoped assistant profile routes for the active conversation."""

from asyncio import to_thread
from datetime import datetime
from importlib.resources import files
from pathlib import Path as FilePath
from typing import Annotated, Protocol, cast

from fastapi import APIRouter, Depends, Path, Request
from fastapi.responses import FileResponse

from bank_agent.api.config import RateClass
from bank_agent.api.dependencies import endpoint, role_dependency, services
from bank_agent.api.errors import ServiceUnavailableError
from bank_agent.api.schemas.preferences import AssistantProfileView, AvatarKey, ChangeAssistantNameRequest
from bank_agent.domain.access import Role
from bank_agent.domain.errors import NotFoundError
from bank_agent.domain.identifiers import ID_PATTERN, ConversationId
from bank_agent.domain.session import Session

router = APIRouter(prefix="/v1", tags=["assistant profile"])
CUSTOMER = frozenset({Role.CUSTOMER})
CustomerSession = Annotated[Session, Depends(role_dependency(CUSTOMER))]
ConversationPath = Annotated[ConversationId, Path(max_length=64, pattern=ID_PATTERN)]
AvatarPath = Annotated[AvatarKey, Path()]


class _ProfileValue(Protocol):
    assistant_name: str
    avatar_key: str
    updated_at: datetime


class _PreferenceValue(Protocol):
    profile: _ProfileValue


class _AssistantPreferences(Protocol):
    """The application service contract; profile reads are the one method not yet present on the service branch."""

    async def get_assistant_profile(
        self, session: Session, conversation_id: ConversationId
    ) -> _PreferenceValue | None: ...

    async def change_assistant_name(
        self, session: Session, conversation_id: ConversationId, name: str
    ) -> _PreferenceValue: ...

    async def mock_assistant_image(self, session: Session, conversation_id: ConversationId) -> _PreferenceValue: ...


def _profile_service(request: Request) -> _AssistantPreferences:
    service = getattr(services(request), "assistant_preferences", None)
    if service is None:
        raise ServiceUnavailableError("assistant preferences are not configured")
    return cast(_AssistantPreferences, service)


def _view(profile: _ProfileValue | None) -> AssistantProfileView:
    name = profile.assistant_name if profile is not None else "Assistant"
    avatar_key = profile.avatar_key if profile is not None else "avatar_1"
    updated_at = profile.updated_at if profile is not None else None
    return AssistantProfileView(
        assistant_name=name,
        avatar_key=cast(AvatarKey, avatar_key),
        avatar_url=f"/api/v1/assistant-profile/avatars/{avatar_key}.png",
        updated_at=updated_at,
    )


_PROFILE_GET = endpoint(rate=RateClass.READ, roles=CUSTOMER, changes_state=False, operation_id="assistant_profile_get")


@router.get("/conversations/{conversation_id}/assistant-profile", response_model=AssistantProfileView, **_PROFILE_GET)
async def get_assistant_profile(
    request: Request, conversation_id: ConversationPath, session: CustomerSession
) -> AssistantProfileView:
    """Read the saved customer profile after the service confirms this conversation belongs to the session."""
    preference = await _profile_service(request).get_assistant_profile(session, conversation_id)
    return _view(preference.profile if preference is not None else None)


_PROFILE_NAME_SET = endpoint(
    rate=RateClass.WRITE, roles=CUSTOMER, changes_state=True, operation_id="assistant_profile_name_set"
)


@router.post(
    "/conversations/{conversation_id}/assistant-profile/name",
    response_model=AssistantProfileView,
    **_PROFILE_NAME_SET,
)
async def change_assistant_name(
    request: Request,
    conversation_id: ConversationPath,
    body: ChangeAssistantNameRequest,
    session: CustomerSession,
) -> AssistantProfileView:
    """Validate and save the assistant name for the signed-in customer's profile."""
    preference = await _profile_service(request).change_assistant_name(session, conversation_id, body.name)
    return _view(preference.profile)


_PROFILE_IMAGE_CHANGE = endpoint(
    rate=RateClass.WRITE, roles=CUSTOMER, changes_state=True, operation_id="assistant_profile_image_change"
)


@router.post(
    "/conversations/{conversation_id}/assistant-profile/mock-image",
    response_model=AssistantProfileView,
    **_PROFILE_IMAGE_CHANGE,
)
async def mock_assistant_image(
    request: Request, conversation_id: ConversationPath, session: CustomerSession
) -> AssistantProfileView:
    """Choose the next predefined PNG through the assistant preference service."""
    preference = await _profile_service(request).mock_assistant_image(session, conversation_id)
    return _view(preference.profile)


_AVATAR_GET = endpoint(rate=RateClass.READ, roles=CUSTOMER, changes_state=False, operation_id="assistant_avatar_get")


@router.get("/assistant-profile/avatars/{avatar_key}.png", include_in_schema=False, **_AVATAR_GET)
async def assistant_avatar(avatar_key: AvatarPath, session: CustomerSession) -> FileResponse:
    """Serve only the packaged PNG variants selected by the preference service."""
    path = FilePath(str(files("bank_agent").joinpath("assets", "avatars", f"{avatar_key}.png")))
    if not await to_thread(path.is_file):
        raise NotFoundError()
    return FileResponse(path, media_type="image/png", filename=f"{avatar_key}.png")
