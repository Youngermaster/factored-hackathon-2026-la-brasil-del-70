"""Product repository port."""

from collections.abc import Sequence
from typing import Protocol

from bank_agent.domain.identifiers import ProductId
from bank_agent.domain.product import Product, ProductStatus, ProductType


class ProductReader(Protocol):
    """Reads the bound customer's products.

    Preconditions: bound to a customer ``AccessContext``.
    Postconditions: only the context customer's products are returned, ordered by ``product_id``.
    Errors: ``AccessContextError`` for a staff context.
    Isolation: another customer's product id returns ``None``, exactly like an unknown id.
    """

    async def get(self, product_id: ProductId) -> Product | None:
        """Return the product, or ``None`` when it is unknown or belongs to another customer."""
        ...

    async def list(self, types: frozenset[ProductType] | None = None) -> Sequence[Product]:
        """Return the customer's products, optionally only the given types."""
        ...


class ProductRepository(ProductReader, Protocol):
    """Adds the one product write the workflow performs: a status change such as a protective card block."""

    async def update_status(
        self, product_id: ProductId, new_status: ProductStatus, *, expected: ProductStatus
    ) -> Product:
        """Compare and set the status, returning the stored product.

        Errors: ``ProductNotFoundError`` for an unknown or foreign id; ``ConcurrencyConflictError`` when the
        current status is not ``expected``. Setting the status it already has, with a matching ``expected``,
        is a no-op that returns the product.
        """
        ...
