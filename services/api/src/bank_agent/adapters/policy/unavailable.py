"""An empty credit catalog, served when the synthetic catalog cannot load and the credit workflow is disabled.

The composition root removes ``credit`` from the enabled workflows at the same time, so no state reaches these
methods through a tool allowlist; they answer as an empty catalog (no product, no display text) rather than raise, so
the HTTP layer's product names and any stray read stay harmless.
"""

from collections.abc import Sequence

from bank_agent.domain.credit import CreditProduct
from bank_agent.domain.identifiers import CreditProductCode
from bank_agent.domain.locale import Country, Language
from bank_agent.policy.loader.catalog import ProductDisplay

UNAVAILABLE_VERSION = "unavailable"


class UnavailableCreditCatalog:
    """Implements ``CreditProductCatalog`` and ``CreditProductNames`` as an empty catalog."""

    def catalog_version(self) -> str:
        return UNAVAILABLE_VERSION

    def list(self, jurisdiction: Country) -> Sequence[CreditProduct]:
        return ()

    def get(self, code: CreditProductCode) -> CreditProduct | None:
        return None

    def display(self, code: CreditProductCode, language: Language) -> ProductDisplay | None:
        return None
