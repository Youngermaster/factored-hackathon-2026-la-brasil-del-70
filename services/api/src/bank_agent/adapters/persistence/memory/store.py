"""Committed in-memory tables and transactional views over them."""

from collections.abc import Iterable
from dataclasses import dataclass, field

from bank_agent.domain.actions import ActionLedgerEntry
from bank_agent.domain.audit import AuditEvent
from bank_agent.domain.complaint import HistoricalComplaint
from bank_agent.domain.conversation import Conversation, Turn
from bank_agent.domain.credit import CreditApplicationIntake, CreditProfile
from bank_agent.domain.customer import Customer
from bank_agent.domain.dispute import DisputeCase
from bank_agent.domain.execution_record import ExecutionRecord
from bank_agent.domain.handoff import Handoff, HandoffRecord
from bank_agent.domain.product import Product
from bank_agent.domain.transaction import Transaction


class TableView[K, V]:
    """A transaction's view of one committed table: reads see its own writes; writes stay private until applied.

    The committed value of every key the view writes is remembered, so ``has_conflict`` can detect that
    another unit of work committed a change to the same key in the meantime (optimistic concurrency).
    """

    def __init__(self, committed: dict[K, V]) -> None:
        self._committed = committed
        self._writes: dict[K, V] = {}
        self._bases: dict[K, V | None] = {}

    def get(self, key: K) -> V | None:
        if key in self._writes:
            return self._writes[key]
        return self._committed.get(key)

    def put(self, key: K, value: V) -> None:
        if key not in self._bases:
            self._bases[key] = self._committed.get(key)
        self._writes[key] = value

    def values(self) -> list[V]:
        return list({**self._committed, **self._writes}.values())

    def has_conflict(self) -> bool:
        return any(self._committed.get(key) is not base for key, base in self._bases.items())

    def apply(self) -> None:
        self._committed.update(self._writes)
        self.discard()

    def discard(self) -> None:
        self._writes.clear()
        self._bases.clear()


class DirectView[K, V](TableView[K, V]):
    """A view whose writes go straight to the committed table, for ports used outside a unit of work."""

    def put(self, key: K, value: V) -> None:
        self._committed[key] = value


@dataclass
class InMemoryStore:
    """The committed state shared by every unit of work of one process (or one test)."""

    customers: dict[str, Customer] = field(default_factory=dict)
    products: dict[str, Product] = field(default_factory=dict)
    transactions: dict[str, Transaction] = field(default_factory=dict)
    complaints: dict[str, HistoricalComplaint] = field(default_factory=dict)
    cases: dict[str, DisputeCase] = field(default_factory=dict)
    conversations: dict[str, Conversation] = field(default_factory=dict)
    turns: dict[str, Turn] = field(default_factory=dict)
    execution_records: dict[str, ExecutionRecord] = field(default_factory=dict)
    handoffs: dict[str, HandoffRecord] = field(default_factory=dict)
    audit_events: dict[str, AuditEvent] = field(default_factory=dict)
    credit_profiles: dict[str, CreditProfile] = field(default_factory=dict)
    """Keyed by customer id: a customer has at most one credit profile."""
    credit_applications: dict[str, CreditApplicationIntake] = field(default_factory=dict)
    action_ledger: dict[tuple[str, str, str], ActionLedgerEntry] = field(default_factory=dict)
    """Keyed by customer id, action, and idempotency key."""

    def seed(
        self,
        *,
        customers: Iterable[Customer] = (),
        products: Iterable[Product] = (),
        transactions: Iterable[Transaction] = (),
        complaints: Iterable[HistoricalComplaint] = (),
        cases: Iterable[DisputeCase] = (),
        conversations: Iterable[Conversation] = (),
        handoffs: Iterable[Handoff] = (),
        credit_profiles: Iterable[CreditProfile] = (),
        credit_applications: Iterable[CreditApplicationIntake] = (),
    ) -> None:
        """Load fixture data directly, bypassing access contexts. For tests, fixtures, and demos only."""
        self.customers.update((item.customer_id, item) for item in customers)
        self.products.update((item.product_id, item) for item in products)
        self.transactions.update((item.transaction_id, item) for item in transactions)
        self.complaints.update((item.complaint_id, item) for item in complaints)
        self.cases.update((item.case_id, item) for item in cases)
        self.conversations.update((item.conversation_id, item) for item in conversations)
        self.handoffs.update((item.handoff_id, HandoffRecord(handoff=item)) for item in handoffs)
        self.credit_profiles.update((item.customer_id, item) for item in credit_profiles)
        self.credit_applications.update((item.application_id, item) for item in credit_applications)
