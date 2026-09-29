"""The customer's assistant profile: the name and the avatar image the chat header shows (ADR 0025).

The profile is presentation only. It never changes what the assistant may do, it holds no customer data beyond
the owning id, and the avatar is one of a fixed set of bundled images: nothing is generated or uploaded. A
customer without a saved profile sees the default one.
"""

from enum import StrEnum
from typing import Annotated, Final

from pydantic import NonNegativeInt, StringConstraints

from bank_agent.domain.base import DomainModel, UtcDatetime
from bank_agent.domain.identifiers import CustomerId

_LETTERS = "A-Za-zÀ-ÖØ-öø-ÿ"
ASSISTANT_NAME_PATTERN: Final = rf"^[{_LETTERS}]+(?:[ '-][{_LETTERS}]+)*$"
"""Letters, including the accented letters of Spanish and Portuguese, in words joined by one space, apostrophe,
or hyphen. No digits, punctuation, markup, or links, so a name can never carry an instruction or a URL."""

AssistantName = Annotated[str, StringConstraints(min_length=1, max_length=40, pattern=ASSISTANT_NAME_PATTERN)]


class AvatarId(StrEnum):
    """The bundled avatar images. The web app serves ``/avatars/<id>.png`` for each member."""

    AVATAR_01 = "avatar-01"
    AVATAR_02 = "avatar-02"
    AVATAR_03 = "avatar-03"
    AVATAR_04 = "avatar-04"
    AVATAR_05 = "avatar-05"
    AVATAR_06 = "avatar-06"


DEFAULT_ASSISTANT_NAME: Final = "Luna"
DEFAULT_AVATAR: Final = AvatarId.AVATAR_01


class AssistantProfile(DomainModel):
    customer_id: CustomerId
    name: AssistantName = DEFAULT_ASSISTANT_NAME
    avatar_id: AvatarId = DEFAULT_AVATAR
    updated_at: UtcDatetime | None = None
    """When the customer last changed the profile; ``None`` for the default profile, which was never saved."""
    version: NonNegativeInt = 0
    """Optimistic concurrency: repositories reject a save whose expected version is stale."""

    @classmethod
    def default(cls, customer_id: CustomerId) -> "AssistantProfile":
        """The profile a customer sees before changing anything."""
        return cls(customer_id=customer_id)

    @property
    def is_default(self) -> bool:
        return self.updated_at is None
