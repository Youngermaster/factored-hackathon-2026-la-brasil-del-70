"""Test support for the banking tools: dependencies over any backend and sessions at a fixed instant."""

from datetime import timedelta

from bank_agent.adapters.persistence.memory.credit_catalog import InMemoryCreditProductCatalog
from bank_agent.adapters.system.ids import RandomIdGenerator
from bank_agent.application.tools.banking import BankingTools, SessionTools
from bank_agent.application.tools.base import ToolDependencies
from bank_agent.application.tools.context import SessionContext, ToolPolicy, ToolSettings
from bank_agent.domain.accounts import CreditBalanceConvention
from bank_agent.domain.actions import ActionKind
from bank_agent.domain.locale import Country
from bank_agent.ports.unit_of_work import UnitOfWorkFactory
from bank_agent.testing.clock import FixedClock
from bank_agent_builders import CUSTOMER_A, T0, session
from bank_agent_credit import CATALOG_VERSION, catalog_products

NOW = T0 + timedelta(minutes=1)
TOOL_POLICY = ToolPolicy(
    max_statement_days=92,
    dispute_sla_days={Country.MX: 45, Country.CO: 15, Country.AR: 30},
    step_up_actions=frozenset(ActionKind),
    pack_version="pack-fixture-0001",
)
"""Fixture tool parameters, equal to the synthetic pack's values; the real pack is loaded in integration tests."""


def tool_dependencies(uow_factory: UnitOfWorkFactory, clock: FixedClock | None = None) -> ToolDependencies:
    return ToolDependencies(
        uow_factory=uow_factory,
        catalog=InMemoryCreditProductCatalog(catalog_products(), CATALOG_VERSION),
        clock=clock or FixedClock(NOW),
        ids=RandomIdGenerator(),
        settings=ToolSettings(policy=TOOL_POLICY, balance_convention=CreditBalanceConvention.BALANCE_IS_AMOUNT_OWED),
    )


def session_context(customer_id: str = CUSTOMER_A, *, step_up: bool = False) -> SessionContext:
    current = session(customer_id=customer_id, session_id=f"ses-{customer_id.lower()}")
    if step_up:
        current = current.with_step_up(now=T0, until=T0 + timedelta(minutes=5))
    return SessionContext.of(current, FixedClock(NOW))


def tools_for(uow_factory: UnitOfWorkFactory, customer_id: str = CUSTOMER_A, *, step_up: bool = False) -> SessionTools:
    return BankingTools(tool_dependencies(uow_factory)).for_session(session_context(customer_id, step_up=step_up))
