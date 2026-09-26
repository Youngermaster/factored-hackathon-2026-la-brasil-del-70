"""Workflow vocabulary shared by the engine, the records, and the contracts."""

from enum import StrEnum
from typing import Annotated

from pydantic import PositiveInt, StringConstraints

from bank_agent.domain.base import DomainModel

StateName = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]{0,63}$")]
"""A workflow state name, for example ``LOCATE_TRANSACTION``. States are defined per workflow in phase 09."""


class Intent(StrEnum):
    DISPUTE_NEW = "dispute_new"
    DISPUTE_STATUS = "dispute_status"
    CARD_BLOCK = "card_block"
    INFORMATIONAL = "informational"
    UNSUPPORTED = "unsupported"
    HUMAN_REQUEST = "human_request"
    GREETING_OR_OTHER = "greeting_or_other"


class Outcome(StrEnum):
    RESOLVED = "resolved"
    CLARIFIED = "clarified"
    ABSTAINED = "abstained"
    ESCALATED = "escalated"
    REFUSED = "refused"
    IN_PROGRESS = "in_progress"


class WorkflowRef(DomainModel):
    """Which workflow definition, and which version of it, handled a turn."""

    id: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
    version: PositiveInt
