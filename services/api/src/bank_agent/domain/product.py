"""Banking products: accounts, cards, loans. Only the fields the dispute and card-block workflow needs."""

from enum import StrEnum
from typing import Self

from bank_agent.domain.base import DomainModel
from bank_agent.domain.errors import InvalidProductStateError
from bank_agent.domain.identifiers import CustomerId, ProductId
from bank_agent.domain.masking import MaskedNumber
from bank_agent.domain.money import Currency


class ProductType(StrEnum):
    CHECKING_ACCOUNT = "checking_account"
    SAVINGS_ACCOUNT = "savings_account"
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    PERSONAL_LOAN = "personal_loan"
    MORTGAGE = "mortgage"
    INVESTMENT = "investment"
    OTHER = "other"
    """Values beyond the documented list (the source list is truncated); phase 03 reports them."""


class ProductStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    CLOSED = "closed"
    SUSPENDED = "suspended"


CARD_TYPES = frozenset({ProductType.CREDIT_CARD, ProductType.DEBIT_CARD})


class Product(DomainModel):
    product_id: ProductId
    customer_id: CustomerId
    product_type: ProductType
    status: ProductStatus
    masked_number: MaskedNumber
    currency: Currency

    @property
    def is_card(self) -> bool:
        return self.product_type in CARD_TYPES

    def blocked(self) -> Self:
        """Return this card blocked. Blocking a blocked card is a no-op.

        Raises ``InvalidProductStateError`` for a product that is not a card, or a card that is closed or
        suspended. Whether a block is allowed in a conversation is decided by policy rules, not here.
        """
        if not self.is_card:
            raise InvalidProductStateError("only cards can be blocked")
        if self.status is ProductStatus.BLOCKED:
            return self
        if self.status is not ProductStatus.ACTIVE:
            raise InvalidProductStateError("only an active card can be blocked")
        return self.evolve(status=ProductStatus.BLOCKED)
