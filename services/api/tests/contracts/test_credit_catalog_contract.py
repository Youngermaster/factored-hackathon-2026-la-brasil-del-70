from collections.abc import Callable

import pytest

from bank_agent.adapters.persistence.memory.credit_catalog import InMemoryCreditProductCatalog
from bank_agent.domain.credit import CreditProductType
from bank_agent.domain.identifiers import CreditProductCode
from bank_agent.domain.locale import Country
from bank_agent.ports.credit_catalog import CreditProductCatalog
from bank_agent_credit import CATALOG_VERSION, catalog_products

CATALOGS = [
    pytest.param(
        lambda: InMemoryCreditProductCatalog(catalog_products(), CATALOG_VERSION), marks=pytest.mark.unit, id="memory"
    )
]


@pytest.mark.parametrize("factory", CATALOGS)
class TestCreditProductCatalogContract:
    def test_lists_a_jurisdictions_products_ordered_by_code(self, factory: Callable[[], CreditProductCatalog]) -> None:
        catalog = factory()
        for country in Country:
            products = catalog.list(country)
            codes = [product.product_code for product in products]
            assert codes == sorted(codes)
            assert len(products) == 2
            assert all(product.jurisdiction is country for product in products)

    def test_every_entry_is_synthetic_and_versioned(self, factory: Callable[[], CreditProductCatalog]) -> None:
        catalog = factory()
        for country in Country:
            for product in catalog.list(country):
                assert product.synthetic is True
                assert product.catalog_version == catalog.catalog_version()

    def test_gets_by_code_and_returns_none_for_unknown(self, factory: Callable[[], CreditProductCatalog]) -> None:
        catalog = factory()
        mortgage = catalog.get(CreditProductCode("CO-MG-FIXTURE"))
        assert mortgage is not None
        assert mortgage.product_type is CreditProductType.MORTGAGE
        assert not mortgage.self_service_eligibility
        assert catalog.get(CreditProductCode("XX-NONE")) is None


@pytest.mark.unit
def test_the_memory_catalog_rejects_repeated_codes_and_foreign_versions() -> None:
    products = catalog_products()
    with pytest.raises(ValueError, match="once"):
        InMemoryCreditProductCatalog((*products, products[0]), CATALOG_VERSION)
    with pytest.raises(ValueError, match="catalog version"):
        InMemoryCreditProductCatalog(products, "another-version")
