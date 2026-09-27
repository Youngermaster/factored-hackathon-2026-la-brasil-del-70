"""What the card support workflow keeps between turns (``WorkflowPosition.data["flow"]``)."""

from typing import Annotated

from pydantic import Field, JsonValue

from bank_agent.application.engine.context import TurnContext
from bank_agent.application.engine.data import dump
from bank_agent.domain.base import DomainModel
from bank_agent.domain.cards import CardAction, CardBlockReason
from bank_agent.domain.identifiers import ProductId
from bank_agent.domain.product import ProductStatus, ProductType
from bank_agent.domain.workflow import Intent

INTENT_ACTIONS = {
    Intent.CARD_BLOCK: CardAction.BLOCK,
    Intent.CARD_UNBLOCK_REQUEST: CardAction.UNBLOCK_REQUEST,
    Intent.CARD_REPLACEMENT_REQUEST: CardAction.REPLACEMENT_REQUEST,
}


class CardData(DomainModel):
    action: CardAction | None = None
    block_reason: CardBlockReason | None = None
    hint_type: ProductType | None = None
    hint_last4: Annotated[str, Field(pattern=r"^[0-9]{4}$")] | None = None
    option_ids: tuple[ProductId, ...] = ()
    product_id: ProductId | None = None
    last4: Annotated[str, Field(pattern=r"^[0-9A-Z]{4}$")] | None = None
    card_type: ProductType | None = None
    status: ProductStatus | None = None
    answered: bool = False
    confirm_shown: bool = False
    block_first: bool = False
    """A lost or stolen card with a replacement request: the protective block is offered before the handoff."""


def load(ctx: TurnContext) -> CardData:
    return CardData.model_validate(ctx.flow) if ctx.flow else CardData()


def save(ctx: TurnContext, data: CardData) -> None:
    flow: dict[str, JsonValue] = dump(data)
    ctx.flow = flow
