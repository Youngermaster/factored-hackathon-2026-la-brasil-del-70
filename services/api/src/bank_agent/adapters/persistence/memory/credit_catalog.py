"""In-memory credit product catalog over given entries; the filesystem catalog (``adapters/policy``) builds on it."""

from collections.abc import Iterable, Sequence

from bank_agent.domain.credit import CreditProduct
from bank_agent.domain.identifiers import CreditProductCode
from bank_agent.domain.locale import Country


class InMemoryCreditProductCatalog:
    """Implements ``CreditProductCatalog``. Rejects repeated codes and entries of another catalog version."""

    def __init__(self, products: Iterable[CreditProduct], catalog_version: str) -> None:
        entries = tuple(products)
        codes = [product.product_code for product in entries]
        if len(set(codes)) != len(codes):
            raise ValueError("a catalog lists each product code once")
        if any(product.catalog_version != catalog_version for product in entries):
            raise ValueError("every catalog entry must carry the catalog version")
        self._products = {product.product_code: product for product in sorted(entries, key=lambda p: p.product_code)}
        self._version = catalog_version

    def catalog_version(self) -> str:
        return self._version

    def list(self, jurisdiction: Country) -> Sequence[CreditProduct]:
        return [product for product in self._products.values() if product.jurisdiction is jurisdiction]

    def get(self, code: CreditProductCode) -> CreditProduct | None:
        return self._products.get(code)
