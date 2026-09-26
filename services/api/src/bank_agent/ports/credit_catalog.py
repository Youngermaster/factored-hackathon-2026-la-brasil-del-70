"""Credit product catalog port (phase 06 adds the filesystem catalog under ``policies/credit/``)."""

from collections.abc import Sequence
from typing import Protocol

from bank_agent.domain.credit import CreditProduct
from bank_agent.domain.identifiers import CreditProductCode
from bank_agent.domain.locale import Country


class CreditProductCatalog(Protocol):
    """The synthetic credit catalog: products, indicative ranges, and the eligibility clauses they bind.

    Preconditions: loaded and validated at startup; ``jurisdiction`` comes from the verified customer profile.
    Postconditions: ``list`` returns the jurisdiction's products ordered by product code; every product is
    labeled synthetic and carries ``catalog_version``, which equals ``catalog_version()``.
    Errors: an unknown code returns ``None`` from ``get``; a malformed catalog is a startup error.
    Isolation: public information only; the catalog holds no customer data and is not customer-scoped.
    """

    def catalog_version(self) -> str:
        """Return the catalog version recorded with every answer."""
        ...

    def list(self, jurisdiction: Country) -> Sequence[CreditProduct]:
        """Return the products offered in ``jurisdiction``."""
        ...

    def get(self, code: CreditProductCode) -> CreditProduct | None:
        """Return the product with ``code``, or ``None``."""
        ...
