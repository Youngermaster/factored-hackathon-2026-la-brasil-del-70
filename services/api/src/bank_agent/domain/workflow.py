"""Workflow vocabulary shared by the engine, the records, and the contracts."""

from enum import StrEnum
from typing import Annotated

from pydantic import PositiveInt, StringConstraints

from bank_agent.domain.base import DomainModel

StateName = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]{0,63}$")]
"""A workflow state name, for example ``LOCATE_TRANSACTION``. States are defined per workflow in phase 09."""


class WorkflowId(StrEnum):
    """The supported workflows (section 1 of CLAUDE.md). ``WorkflowRef.id`` stays a pattern-constrained string in
    every contract; membership in this registry is checked by the application, not by the schemas."""

    ACCOUNT_INQUIRY = "account_inquiry"
    CARD_SUPPORT = "card_support"
    DISPUTE = "dispute"
    CREDIT = "credit"


class Intent(StrEnum):
    """What the customer wants. Each intent is owned by exactly one workflow or is cross-workflow.

    ``domain.workflow_catalog.WORKFLOW_CATALOG`` assigns the owners; ``CROSS_WORKFLOW_INTENTS`` lists the rest.
    """

    DISPUTE_NEW = "dispute_new"
    DISPUTE_STATUS = "dispute_status"
    CARD_BLOCK = "card_block"
    INFORMATIONAL = "informational"
    UNSUPPORTED = "unsupported"
    HUMAN_REQUEST = "human_request"
    GREETING_OR_OTHER = "greeting_or_other"
    BALANCE_INQUIRY = "balance_inquiry"
    PAYMENT_STATUS = "payment_status"
    STATEMENT_REQUEST = "statement_request"
    CARD_STATUS = "card_status"
    CARD_UNBLOCK_REQUEST = "card_unblock_request"
    CARD_REPLACEMENT_REQUEST = "card_replacement_request"
    CREDIT_PRODUCT_INFO = "credit_product_info"
    CREDIT_ELIGIBILITY = "credit_eligibility"
    CREDIT_APPLICATION = "credit_application"
    CREDIT_APPLICATION_STATUS = "credit_application_status"


CROSS_WORKFLOW_INTENTS = frozenset(
    {Intent.INFORMATIONAL, Intent.UNSUPPORTED, Intent.HUMAN_REQUEST, Intent.GREETING_OR_OTHER}
)
"""Intents no workflow owns: the engine answers, clarifies, abstains, or hands off from any workflow."""


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
