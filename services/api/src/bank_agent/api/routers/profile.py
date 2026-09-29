"""``/v1/profile``: the signed-in customer's first name and assistant profile, for the chat header.

The customer comes only from the session. Changes to the assistant's name and image happen in the chat through
the ``change_assistant_name`` and ``mock_assistant_image`` tools, so this router is read only.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from bank_agent.api.config import RateClass
from bank_agent.api.dependencies import endpoint, role_dependency, services
from bank_agent.api.schemas.profile import AssistantProfileView, ProfileView
from bank_agent.domain.access import Role
from bank_agent.domain.session import Session

router = APIRouter(prefix="/v1/profile", tags=["profile"])
CUSTOMER = frozenset({Role.CUSTOMER})
CustomerSession = Annotated[Session, Depends(role_dependency(CUSTOMER))]

_PROFILE_GET = endpoint(rate=RateClass.READ, roles=CUSTOMER, changes_state=False, operation_id="profile_get")


@router.get("", response_model=ProfileView, **_PROFILE_GET)
async def get_profile(request: Request, session: CustomerSession) -> ProfileView:
    """The customer's first name and the assistant's name and avatar image."""
    profile = await services(request).profiles.current(session)
    return ProfileView(customer_first_name=profile.first_name, assistant=AssistantProfileView.of(profile.assistant))
