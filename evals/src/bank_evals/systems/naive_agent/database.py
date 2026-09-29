"""B1's isolated evaluation database (schema ``eval_naive``): an in-memory copy of the evaluation world per case.

It is never the application database: B1 has no unit of work, no row-level security, and no connection string.
Every read takes the customer id the model passes, so a model that passes another customer's id reads that
customer's records; that is the naive design the baseline measures, and the graders count such disclosures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bank_agent.domain.product import Product, ProductStatus
from bank_agent.domain.transaction import Transaction
from bank_evals.world.model import World

SCHEMA = "eval_naive"


@dataclass
class NaiveHandoff:
    customer_id: str
    reason: str
    request: str
    verified_facts: list[str]
    actions_taken: list[str]
    open_questions: list[str]


@dataclass
class NaiveDatabase:
    world: World
    new_cases: list[dict[str, Any]] = field(default_factory=list)
    new_applications: list[dict[str, Any]] = field(default_factory=list)
    handoffs: list[NaiveHandoff] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    schema: str = SCHEMA

    def customer_country(self, customer_id: str) -> str | None:
        found = next((p.customer for p in self.world.personas.values() if p.customer.customer_id == customer_id), None)
        return found.country.value if found is not None else None

    def products(self, customer_id: str) -> list[Product]:
        return [p for p in self.world.products if p.customer_id == customer_id]

    def transactions(self, customer_id: str) -> list[Transaction]:
        return sorted(
            (t for t in self.world.transactions if t.customer_id == customer_id),
            key=lambda t: t.occurred_at,
            reverse=True,
        )

    def block(self, product_id: str) -> bool:
        product = next((p for p in self.world.products if p.product_id == product_id), None)
        if product is None:
            return False
        self.world.replace_product(product.evolve(status=ProductStatus.BLOCKED))
        self.blocked.append(product_id)
        return True
