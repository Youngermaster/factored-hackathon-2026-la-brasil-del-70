"""The phase 02b implementations satisfy their ports (checked by mypy through the typed assignments)."""

from bank_agent.adapters.persistence.memory.credit_catalog import InMemoryCreditProductCatalog
from bank_agent.adapters.persistence.memory.store import InMemoryStore
from bank_agent.adapters.persistence.memory.unit_of_work import InMemoryUnitOfWork
from bank_agent.domain.access import AccessContext
from bank_agent.domain.identifiers import CustomerId
from bank_agent.ports.credit_catalog import CreditProductCatalog
from bank_agent.ports.eligibility import EligibilityPolicy
from bank_agent.ports.models import RiskEstimator
from bank_agent.ports.repositories.credit_applications import CreditApplicationRepository
from bank_agent.ports.repositories.credit_profiles import CreditProfileReader
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.credit import FakeEligibilityPolicy, FakeRiskEstimator
from bank_agent.testing.ids import SequentialIdGenerator
from bank_agent_builders import CUSTOMER_A, T0
from bank_agent_credit import CATALOG_VERSION, catalog_products


def test_credit_implementations_satisfy_their_ports() -> None:
    uow = InMemoryUnitOfWork(InMemoryStore(), AccessContext.for_customer(CustomerId(CUSTOMER_A)))
    estimator: RiskEstimator = FakeRiskEstimator(FixedClock(T0), SequentialIdGenerator())
    policy: EligibilityPolicy = FakeEligibilityPolicy(FixedClock(T0), SequentialIdGenerator())
    catalog: CreditProductCatalog = InMemoryCreditProductCatalog(catalog_products(), CATALOG_VERSION)
    profiles: CreditProfileReader = uow.credit_profiles
    applications: CreditApplicationRepository = uow.credit_applications
    assert all(item is not None for item in (estimator, policy, catalog, profiles, applications))
