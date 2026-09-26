"""Card support vocabulary: what a customer can ask about a card, and how a card's status is shown.

A protective block is a self-service write (confirmation, step-up, verified read-back). Unblocking a card and
issuing a replacement need identity and fraud checks the prototype cannot verify, so they are escalation-only:
no tool performs them, and the request goes to a human with a dedicated reason code. The full handling table,
which names the write action and the reason codes, is ``workflow_catalog.CARD_ACTION_HANDLING``.

Declined card transactions are found through ``TransactionQuery(statuses=(declined,))``. The dataset's
``response_code`` is not interpreted, because the data has no code table.
"""

from datetime import date
from enum import StrEnum
from typing import Self

from pydantic import model_validator

from bank_agent.domain.base import DomainModel
from bank_agent.domain.identifiers import SourceRef, SourceTable
from bank_agent.domain.masking import MaskedNumber
from bank_agent.domain.product import CARD_TYPES, Product, ProductStatus, ProductType


class CardAction(StrEnum):
    BLOCK = "block"
    UNBLOCK_REQUEST = "unblock_request"
    REPLACEMENT_REQUEST = "replacement_request"


SELF_SERVICE_CARD_ACTIONS = frozenset({CardAction.BLOCK})
ESCALATION_ONLY_CARD_ACTIONS = frozenset({CardAction.UNBLOCK_REQUEST, CardAction.REPLACEMENT_REQUEST})


class CardBlockReason(StrEnum):
    LOST = "lost"
    STOLEN = "stolen"
    UNRECOGNIZED_ACTIVITY = "unrecognized_activity"
    PRECAUTION = "precaution"


def _require_product_ref(ref: SourceRef) -> None:
    if ref.table is not SourceTable.PRODUCTS:
        raise ValueError("a card reference must point to the products table")


class CardStatusView(DomainModel):
    """A card's status as shown to its owner. ``product_ref`` is grounding evidence, never displayed."""

    product_ref: SourceRef
    card_type: ProductType
    masked_number: MaskedNumber
    status: ProductStatus
    expires_on: date | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        _require_product_ref(self.product_ref)
        if self.card_type not in CARD_TYPES:
            raise ValueError("a card status view is for credit and debit cards only")
        return self

    @classmethod
    def from_product(cls, product: Product) -> Self:
        return cls(
            product_ref=SourceRef.of(SourceTable.PRODUCTS, product.product_id),
            card_type=product.product_type,
            masked_number=product.masked_number,
            status=product.status,
            expires_on=product.expires_on,
        )


class CardRequest(DomainModel):
    """The card request a handoff carries: what the customer asked for, and for which card."""

    action: CardAction
    product_ref: SourceRef

    @model_validator(mode="after")
    def _validate(self) -> Self:
        _require_product_ref(self.product_ref)
        return self
