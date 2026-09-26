"""Card and account transactions.

``merchant_name`` is untrusted record text and an indirect prompt-injection surface. ``fraud`` holds the
bank's fraud label and score: internal routing context that is never rendered to customers or sent to a model.
"""

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, StringConstraints, model_validator

from bank_agent.domain.base import DomainModel, Internal, UntrustedText, UtcDatetime
from bank_agent.domain.identifiers import CustomerId, ProductId, TransactionId
from bank_agent.domain.locale import CountryCode
from bank_agent.domain.money import Amount, Currency, Money


class TransactionType(StrEnum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    PAYMENT = "payment"
    PURCHASE = "purchase"
    ADJUSTMENT = "adjustment"


class TransactionCategory(StrEnum):
    FOOD = "food"
    TRANSPORT = "transport"
    SERVICES = "services"
    ENTERTAINMENT = "entertainment"
    HEALTH = "health"
    OTHER = "other"


class TransactionChannel(StrEnum):
    ATM = "atm"
    BRANCH = "branch"
    WEB = "web"
    APP = "app"
    POS = "pos"
    TRANSFER = "transfer"


class TransactionStatus(StrEnum):
    APPROVED = "approved"
    DECLINED = "declined"
    PENDING = "pending"
    REVERSED = "reversed"


class FraudContext(DomainModel):
    """The bank's existing fraud label and score (0 to 100)."""

    label: bool
    score: Annotated[Amount, Field(ge=0, le=100)] | None = None


MerchantText = Annotated[UntrustedText, StringConstraints(max_length=150)]


class Transaction(DomainModel):
    transaction_id: TransactionId
    customer_id: CustomerId
    product_id: ProductId
    occurred_at: UtcDatetime
    transaction_type: TransactionType
    category: TransactionCategory | None = None
    amount: Money
    amount_usd: Money | None = None
    channel: TransactionChannel
    status: TransactionStatus
    merchant_name: MerchantText | None = None
    merchant_category: Annotated[str, StringConstraints(max_length=50)] | None = None
    location_country: CountryCode
    location_city: Annotated[str, StringConstraints(max_length=100)] | None = None
    fraud: Annotated[FraudContext, Internal()] = Field(repr=False)

    @model_validator(mode="after")
    def _validate_usd(self) -> Self:
        if self.amount_usd is not None and self.amount_usd.currency is not Currency.USD:
            raise ValueError("amount_usd must be in USD")
        return self

    @property
    def fraud_score(self) -> Decimal | None:
        return self.fraud.score
