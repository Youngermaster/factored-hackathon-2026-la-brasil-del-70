"""Banking products: accounts, cards, loans.

The balance, limit, rate, and date fields are optional: they arrived with the account inquiry and credit
workflows, and every one of them may be missing in the source data. ``days_past_due`` is internal credit
information, never shown to customers or sent to a model.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, NonNegativeInt, model_validator

from bank_agent.domain.base import DomainModel, Internal, UtcDatetime
from bank_agent.domain.errors import InvalidProductStateError
from bank_agent.domain.identifiers import CustomerId, ProductId
from bank_agent.domain.masking import MaskedNumber
from bank_agent.domain.money import Amount, Currency, Money


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
CREDIT_PRODUCT_TYPES = frozenset({ProductType.CREDIT_CARD, ProductType.PERSONAL_LOAN, ProductType.MORTGAGE})

MAX_ANNUAL_RATE = Decimal("999.99")
"""``interest_rate`` is ``DECIMAL(5,2)``; annual rates above 100 percent occur (for example in Argentina)."""


class Product(DomainModel):
    product_id: ProductId
    customer_id: CustomerId
    product_type: ProductType
    status: ProductStatus
    masked_number: MaskedNumber
    currency: Currency
    current_balance: Money | None = None
    credit_limit: Money | None = None
    annual_interest_rate: Annotated[Amount, Field(ge=0, le=MAX_ANNUAL_RATE)] | None = None
    """Annual percent, for example ``45.00``."""
    opened_on: date | None = None
    expires_on: date | None = None
    balance_as_of: UtcDatetime | None = None
    """When ``current_balance`` was true. The data is a monthly snapshot, so every balance answer states it."""
    days_past_due: Annotated[NonNegativeInt | None, Internal()] = None

    @model_validator(mode="after")
    def _validate_amounts(self) -> Self:
        for amount in (self.current_balance, self.credit_limit):
            if amount is not None and amount.currency is not self.currency:
                raise ValueError("product amounts must be in the product currency")
        if self.credit_limit is not None and self.credit_limit.amount < 0:
            raise ValueError("a credit limit cannot be negative")
        if self.current_balance is not None and self.balance_as_of is None:
            raise ValueError("a balance needs the instant it was true (balance_as_of)")
        return self

    @property
    def is_card(self) -> bool:
        return self.product_type in CARD_TYPES

    @property
    def is_credit_product(self) -> bool:
        return self.product_type in CREDIT_PRODUCT_TYPES

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
