"""HTTP schemas for the customer's saved assistant profile."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import StringConstraints

from bank_agent.api.schemas.base import RequestModel, ResponseModel

AvatarKey = Literal["avatar_1", "avatar_2"]
AssistantName = Annotated[str, StringConstraints(min_length=1, max_length=256)]


class ChangeAssistantNameRequest(RequestModel):
    name: AssistantName


class AssistantProfileView(ResponseModel):
    assistant_name: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    avatar_key: AvatarKey
    avatar_url: str
    updated_at: datetime | None
