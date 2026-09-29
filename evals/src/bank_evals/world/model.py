"""The evaluation world: team-made, synthetic records that every system under test starts from.

The world is not organizer data (CLAUDE.md rule 5): every name, identifier, merchant, and amount below is
invented for the evaluation and labeled synthetic. Personas mirror the named selection criteria of
``data_platform/seed/personas.yaml``. Scenarios never name identifiers; they name a persona (``persona_ref``) and
its records by symbolic references (``recent_card_purchase``), which ``World.resolve`` turns into identifiers.

Every case runs on a fresh ``World.copy()``, so writes from one case never reach another.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Final

from bank_agent.domain.complaint import HistoricalComplaint
from bank_agent.domain.credit import CreditApplicationIntake, CreditProfile
from bank_agent.domain.customer import Customer
from bank_agent.domain.dispute import DisputeCase
from bank_agent.domain.product import Product
from bank_agent.domain.transaction import Transaction

NOW: Final = datetime(2026, 6, 18, 15, 0, tzinfo=UTC)
"""The evaluation clock: one day after the data as-of date, as in the workflow tests."""
AS_OF: Final = datetime(2026, 6, 17, 12, 0, tzinfo=UTC)
WORLD_VERSION: Final = "eval-world-1"


class UnknownRecordError(LookupError):
    """A scenario names a persona or a record the world does not have."""


@dataclass(frozen=True)
class Persona:
    """One synthetic customer and the symbolic names of their records."""

    persona_id: str
    customer: Customer
    demonstrates: str
    refs: dict[str, str] = field(default_factory=dict)
    """Symbolic record name to record identifier (a product, transaction, case, or application)."""


@dataclass
class World:
    personas: dict[str, Persona] = field(default_factory=dict)
    products: list[Product] = field(default_factory=list)
    transactions: list[Transaction] = field(default_factory=list)
    complaints: list[HistoricalComplaint] = field(default_factory=list)
    cases: list[DisputeCase] = field(default_factory=list)
    credit_profiles: list[CreditProfile] = field(default_factory=list)
    credit_applications: list[CreditApplicationIntake] = field(default_factory=list)
    version: str = WORLD_VERSION

    @property
    def customers(self) -> list[Customer]:
        return [persona.customer for persona in self.personas.values()]

    def persona(self, persona_ref: str) -> Persona:
        try:
            return self.personas[persona_ref]
        except KeyError:
            raise UnknownRecordError(f"no persona {persona_ref!r} in {self.version}") from None

    def resolve(self, persona_ref: str, record_ref: str) -> str:
        """The identifier behind ``record_ref`` for ``persona_ref``."""
        persona = self.persona(persona_ref)
        try:
            return persona.refs[record_ref]
        except KeyError:
            raise UnknownRecordError(f"persona {persona_ref!r} has no record {record_ref!r}") from None

    def copy(self) -> World:
        """A deep copy for one case: domain objects are immutable, the collections are not."""
        return World(
            personas=dict(self.personas),
            products=list(self.products),
            transactions=list(self.transactions),
            complaints=list(self.complaints),
            cases=list(self.cases),
            credit_profiles=list(self.credit_profiles),
            credit_applications=list(self.credit_applications),
            version=self.version,
        )

    def product(self, product_id: str) -> Product:
        return next(item for item in self.products if item.product_id == product_id)

    def transaction(self, transaction_id: str) -> Transaction:
        return next(item for item in self.transactions if item.transaction_id == transaction_id)

    def replace_product(self, product: Product) -> None:
        self.products = [product if item.product_id == product.product_id else item for item in self.products]

    def replace_transaction(self, transaction: Transaction) -> None:
        self.transactions = [
            transaction if item.transaction_id == transaction.transaction_id else item for item in self.transactions
        ]

    def replace_profile(self, profile: CreditProfile) -> None:
        self.credit_profiles = [
            profile if item.customer_id == profile.customer_id else item for item in self.credit_profiles
        ]

    def snapshot(self) -> World:
        return copy.deepcopy(self)
