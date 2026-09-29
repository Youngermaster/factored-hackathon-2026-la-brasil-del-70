"""Customer-wide preferences for the assistant shown in chat."""

from datetime import datetime

from bank_agent.domain.base import DomainModel
from bank_agent.domain.identifiers import CustomerId


class AssistantProfile(DomainModel):
    customer_id: CustomerId
    assistant_name: str
    avatar_key: str
    updated_at: datetime
