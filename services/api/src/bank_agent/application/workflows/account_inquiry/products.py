"""The session customer's own products, as the account workflow offers and narrows them (never another customer's:
the tools are scoped by the session)."""

from dataclasses import dataclass

from bank_agent.application.engine.context import TurnContext
from bank_agent.application.workflows.account_inquiry.data import AccountData
from bank_agent.domain.identifiers import ProductId, SourceRef
from bank_agent.domain.product import ProductType


@dataclass(frozen=True)
class ProductOption:
    ref: SourceRef
    product_type: ProductType
    last4: str

    @property
    def product_id(self) -> ProductId:
        return ProductId(self.ref.key)


async def my_products(ctx: TurnContext) -> list[ProductOption]:
    """The customer's products with a balance and their cards, once each, ordered by product id."""
    found: dict[str, ProductOption] = {}
    for balance in await ctx.tools.list_my_balances():
        found[balance.product_ref.key] = ProductOption(
            balance.product_ref, balance.product_type, balance.masked_number.last4
        )
    for card in await ctx.tools.list_my_cards():
        found.setdefault(
            card.product_ref.key, ProductOption(card.product_ref, card.card_type, card.masked_number.last4)
        )
    return [found[key] for key in sorted(found)]


def narrowed(data: AccountData, products: list[ProductOption]) -> list[ProductOption]:
    """Products matching the customer's ending and type hints; all of them when a hint matches none."""
    chosen = products
    if data.hint_last4 is not None:
        chosen = [p for p in chosen if p.last4 == data.hint_last4] or chosen
    if data.hint_type is not None:
        chosen = [p for p in chosen if p.product_type is data.hint_type] or chosen
    return chosen
