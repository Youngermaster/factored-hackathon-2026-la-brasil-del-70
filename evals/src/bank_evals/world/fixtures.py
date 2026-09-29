"""Apply a scenario's record fixtures to a case's copy of the world.

Record fixtures change the data before the conversation starts (an injected merchant name, a product status, an
existing case or application, a missing credit fact). Run-time fixtures (a session expiry before a turn, a model
that is unavailable) are read by the user driver and the systems, not here.
"""

from datetime import timedelta

from bank_agent.domain.base import UntrustedText
from bank_agent.domain.credit import CreditApplicationIntake
from bank_agent.domain.dispute import DisputeCase
from bank_agent.domain.money import Money
from bank_evals.scenarios.model import (
    CreditProfileOverride,
    ExistingCase,
    ExistingCreditApplication,
    MerchantNameOverride,
    ProductStatusOverride,
    Scenario,
)
from bank_evals.world.model import NOW, World


def apply_fixtures(scenario: Scenario, world: World) -> World:
    """``world`` (a copy owned by the case) with the scenario's record fixtures applied."""
    persona = scenario.persona_ref
    for index, fixture in enumerate(scenario.fixtures):
        if isinstance(fixture, MerchantNameOverride):
            txn = world.transaction(world.resolve(persona, fixture.transaction_ref))
            world.replace_transaction(txn.evolve(merchant_name=UntrustedText(fixture.value)))
        elif isinstance(fixture, ProductStatusOverride):
            product = world.product(world.resolve(persona, fixture.product_ref))
            world.replace_product(product.evolve(status=fixture.status))
        elif isinstance(fixture, ExistingCase):
            txn = world.transaction(world.resolve(persona, fixture.transaction_ref))
            opened = NOW - timedelta(days=3)
            case = DisputeCase.open(
                case_id=f"case-fixture-{scenario.id[:40]}-{index}",  # type: ignore[arg-type]
                transaction=txn,
                reason=fixture.reason,
                opened_at=opened,
                sla_due_at=opened + timedelta(days=15),
                idempotency_key=f"idem-fixture-{index}-{scenario.id[:40]}",  # type: ignore[arg-type]
            )
            world.cases.append(case.evolve(status=fixture.status))
        elif isinstance(fixture, CreditProfileOverride):
            profile = next(
                p for p in world.credit_profiles if p.customer_id == world.persona(persona).customer.customer_id
            )
            value = fixture.value
            if fixture.fact == "estimated_monthly_income" and isinstance(value, Money):
                value = Money.of(str(value.amount), value.currency)
            world.replace_profile(profile.evolve(**{fixture.fact: value}))
        elif isinstance(fixture, ExistingCreditApplication):
            customer = world.persona(persona).customer
            intake = CreditApplicationIntake.submit(
                application_id=f"app-fixture-{index}-{scenario.id[:40]}",  # type: ignore[arg-type]
                customer_id=customer.customer_id,
                product_code=fixture.product_code,
                requested_amount=Money.of("10000.00", _currency(world, persona)),
                requested_term_months=24,
                purpose="general_purpose",
                idempotency_key=f"idem-fixture-app-{index}-{scenario.id[:40]}",  # type: ignore[arg-type]
                created_at=NOW - timedelta(days=4),
            )
            world.credit_applications.append(intake.evolve(status=fixture.status))
    return world


def _currency(world: World, persona: str):  # type: ignore[no-untyped-def]
    customer = world.persona(persona).customer
    return next(p.currency for p in world.products if p.customer_id == customer.customer_id)
