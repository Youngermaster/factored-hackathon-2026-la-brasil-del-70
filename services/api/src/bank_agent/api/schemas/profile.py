"""The profile the chat header shows: the customer's first name and the assistant's name and avatar image."""

from datetime import datetime

from pydantic import Field

from bank_agent.api.schemas.base import ResponseModel
from bank_agent.domain.assistant_profile import AssistantProfile, AvatarId

AVATAR_PATH_PREFIX = "/avatars/"
"""The web app serves the bundled images at ``/avatars/<avatar_id>.png``; the API never serves or accepts images."""


class AssistantProfileView(ResponseModel):
    name: str
    avatar_id: AvatarId
    avatar_url: str = Field(description="Path of the bundled PNG in the web app, for example `/avatars/avatar-01.png`.")
    updated_at: datetime | None = Field(description="When the customer last changed the profile; null for the default.")

    @classmethod
    def of(cls, profile: AssistantProfile) -> "AssistantProfileView":
        return cls(
            name=profile.name,
            avatar_id=profile.avatar_id,
            avatar_url=f"{AVATAR_PATH_PREFIX}{profile.avatar_id.value}.png",
            updated_at=profile.updated_at,
        )


class ProfileView(ResponseModel):
    customer_first_name: str
    assistant: AssistantProfileView
