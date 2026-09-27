"""Tool argument and result models that the domain does not already define."""

from datetime import date
from typing import Annotated, Self

from pydantic import Field, model_validator

from bank_agent.domain.base import DomainModel, UtcDatetime
from bank_agent.domain.identifiers import ProductId, SourceRef, SourceTable
from bank_agent.domain.masking import MaskedNumber
from bank_agent.domain.money import Amount
from bank_agent.domain.product import Product, ProductStatus, ProductType
from bank_agent.domain.transaction import TransactionStatus
from bank_agent.ports.repositories.transactions import MAX_TRANSACTION_PAGE


class ProductStatusView(DomainModel):
    """What ``get_product_status`` returns: status and expiry, never balances or internal credit facts."""

    product_ref: SourceRef
    product_type: ProductType
    masked_number: MaskedNumber
    status: ProductStatus
    expires_on: date | None = None

    @classmethod
    def from_product(cls, product: Product) -> Self:
        return cls(
            product_ref=SourceRef.of(SourceTable.PRODUCTS, product.product_id),
            product_type=product.product_type,
            masked_number=product.masked_number,
            status=product.status,
            expires_on=product.expires_on,
        )


class PaymentFilter(DomainModel):
    """Filters for ``get_payment_status``; the type filter (payments and transfers) is fixed by the tool."""

    occurred_from: UtcDatetime | None = None
    occurred_to: UtcDatetime | None = None
    product_ids: tuple[ProductId, ...] = ()
    statuses: tuple[TransactionStatus, ...] = ()
    min_amount: Amount | None = None
    max_amount: Amount | None = None
    limit: Annotated[int, Field(ge=1, le=MAX_TRANSACTION_PAGE)] = 20

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.occurred_from and self.occurred_to and self.occurred_to < self.occurred_from:
            raise ValueError("occurred_to cannot precede occurred_from")
        return self
