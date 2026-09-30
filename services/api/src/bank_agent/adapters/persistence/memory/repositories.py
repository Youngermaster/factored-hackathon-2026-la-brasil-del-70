"""In-memory repositories. Each is bound to an ``AccessContext`` and to table views of one unit of work."""

from collections.abc import Sequence
from datetime import datetime

from bank_agent.adapters.persistence.memory.store import TableView
from bank_agent.domain.access import AccessContext, Role
from bank_agent.domain.actions import ActionKind, ActionLedgerEntry
from bank_agent.domain.audit import AuditEvent
from bank_agent.domain.complaint import HistoricalComplaint
from bank_agent.domain.conversation import Conversation, Turn
from bank_agent.domain.credit import (
    CUSTOMER_APPLICATION_TRANSITIONS,
    REVIEWABLE_APPLICATION_STATUSES,
    REVIEWER_APPLICATION_TRANSITIONS,
    ApplicationStatus,
    CreditApplicationIntake,
    CreditProfile,
)
from bank_agent.domain.customer import Customer
from bank_agent.domain.dispute import DisputeCase, DisputeStatus
from bank_agent.domain.errors import (
    AccessContextError,
    AppendOnlyViolationError,
    CaseNotFoundError,
    ConcurrencyConflictError,
    ConversationNotFoundError,
    CreditApplicationNotFoundError,
    CustomerNotFoundError,
    DuplicateEntityError,
    HandoffNotFoundError,
    IdempotencyConflictError,
    ProductNotFoundError,
)
from bank_agent.domain.execution_record import ExecutionRecord
from bank_agent.domain.handoff import Handoff, HandoffOutcomeCode, HandoffRecord
from bank_agent.domain.identifiers import (
    ApplicationId,
    CaseId,
    ConversationId,
    CustomerId,
    HandoffId,
    IdempotencyKey,
    ProductId,
    StaffId,
    TransactionId,
    TurnId,
)
from bank_agent.domain.product import Product, ProductStatus, ProductType
from bank_agent.domain.transaction import Transaction
from bank_agent.ports.audit import AuditQuery
from bank_agent.ports.repositories.handoffs import HandoffQuery
from bank_agent.ports.repositories.transactions import TransactionQuery


def _customer_of(context: AccessContext) -> CustomerId:
    if context.role is not Role.CUSTOMER or context.customer_id is None:
        raise AccessContextError("this operation needs a customer context")
    return context.customer_id


def _staff_of(context: AccessContext, role: Role) -> StaffId:
    if context.role is not role or context.staff_id is None:
        raise AccessContextError(f"this operation needs a {role.value} context")
    return context.staff_id


class InMemoryCustomerRepository:
    def __init__(self, customers: TableView[str, Customer], context: AccessContext) -> None:
        self._customers = customers
        self._context = context

    async def get_current(self) -> Customer:
        customer = self._customers.get(_customer_of(self._context))
        if customer is None:
            raise CustomerNotFoundError()
        return customer


class InMemoryProductRepository:
    def __init__(self, products: TableView[str, Product], context: AccessContext) -> None:
        self._products = products
        self._context = context

    async def get(self, product_id: ProductId) -> Product | None:
        owner = _customer_of(self._context)
        product = self._products.get(product_id)
        return product if product is not None and product.customer_id == owner else None

    async def list(self, types: frozenset[ProductType] | None = None) -> Sequence[Product]:
        owner = _customer_of(self._context)
        found = [
            product
            for product in self._products.values()
            if product.customer_id == owner and (types is None or product.product_type in types)
        ]
        return sorted(found, key=lambda product: product.product_id)

    async def update_status(
        self, product_id: ProductId, new_status: ProductStatus, *, expected: ProductStatus
    ) -> Product:
        current = await self.get(product_id)
        if current is None:
            raise ProductNotFoundError()
        if current.status is not expected:
            raise ConcurrencyConflictError("the product status changed")
        if current.status is new_status:
            return current
        updated = current.blocked() if new_status is ProductStatus.BLOCKED else current.evolve(status=new_status)
        self._products.put(product_id, updated)
        return updated


class InMemoryTransactionRepository:
    def __init__(self, transactions: TableView[str, Transaction], context: AccessContext) -> None:
        self._transactions = transactions
        self._context = context

    async def get(self, transaction_id: TransactionId) -> Transaction | None:
        owner = _customer_of(self._context)
        transaction = self._transactions.get(transaction_id)
        return transaction if transaction is not None and transaction.customer_id == owner else None

    async def list(self, query: TransactionQuery) -> Sequence[Transaction]:
        owner = _customer_of(self._context)

        def matches(txn: Transaction) -> bool:
            return (
                txn.customer_id == owner
                and (query.occurred_from is None or txn.occurred_at >= query.occurred_from)
                and (query.occurred_to is None or txn.occurred_at <= query.occurred_to)
                and (not query.product_ids or txn.product_id in query.product_ids)
                and (not query.statuses or txn.status in query.statuses)
                and (not query.types or txn.transaction_type in query.types)
                and (query.min_amount is None or txn.amount.amount >= query.min_amount)
                and (query.max_amount is None or txn.amount.amount <= query.max_amount)
            )

        found = [txn for txn in self._transactions.values() if matches(txn)]
        found.sort(key=lambda txn: txn.transaction_id)
        found.sort(key=lambda txn: txn.occurred_at, reverse=True)
        return found[: query.limit]


class InMemoryHistoricalComplaintRepository:
    def __init__(self, complaints: TableView[str, HistoricalComplaint], context: AccessContext) -> None:
        self._complaints = complaints
        self._context = context

    async def list_since(self, since: datetime) -> Sequence[HistoricalComplaint]:
        owner = _customer_of(self._context)
        found = [item for item in self._complaints.values() if item.customer_id == owner and item.created_at >= since]
        found.sort(key=lambda item: item.complaint_id)
        found.sort(key=lambda item: item.created_at, reverse=True)
        return found

    async def count_since(self, since: datetime) -> int:
        return len(await self.list_since(since))


def _same_request(left: DisputeCase, right: DisputeCase) -> bool:
    return (left.transaction_id, left.reason, left.disputed_amount) == (
        right.transaction_id,
        right.reason,
        right.disputed_amount,
    )


class InMemoryCaseRepository:
    def __init__(
        self, cases: TableView[str, DisputeCase], handoffs: TableView[str, HandoffRecord], context: AccessContext
    ) -> None:
        self._cases = cases
        self._handoffs = handoffs
        self._context = context

    def _own(self) -> list[DisputeCase]:
        owner = _customer_of(self._context)
        return [case for case in self._cases.values() if case.customer_id == owner]

    async def get(self, case_id: CaseId) -> DisputeCase | None:
        case = self._cases.get(case_id)
        if self._context.role is Role.AGENT:
            referenced = any(record.handoff.case_ref == case_id for record in self._handoffs.values())
            return case if referenced else None
        owner = _customer_of(self._context)
        return case if case is not None and case.customer_id == owner else None

    async def list(self, statuses: frozenset[DisputeStatus] | None = None, limit: int = 50) -> Sequence[DisputeCase]:
        found = [case for case in self._own() if statuses is None or case.status in statuses]
        found.sort(key=lambda case: case.case_id)
        found.sort(key=lambda case: case.opened_at, reverse=True)
        return found[:limit]

    async def find_by_idempotency_key(self, key: IdempotencyKey) -> DisputeCase | None:
        return next((case for case in self._own() if case.idempotency_key == key), None)

    async def find_open_for_transaction(self, transaction_id: TransactionId) -> DisputeCase | None:
        open_cases = [case for case in self._own() if case.transaction_id == transaction_id and case.is_open]
        return max(open_cases, key=lambda case: (case.opened_at, case.case_id), default=None)

    async def add(self, case: DisputeCase) -> DisputeCase:
        if case.customer_id != _customer_of(self._context):
            raise AccessContextError("a case can only be added for the context customer")
        existing = await self.find_by_idempotency_key(case.idempotency_key)
        if existing is not None:
            if _same_request(existing, case):
                return existing
            raise IdempotencyConflictError()
        if self._cases.get(case.case_id) is not None:
            raise DuplicateEntityError("a case with this id already exists")
        self._cases.put(case.case_id, case)
        return case

    async def update(self, case: DisputeCase, *, expected_version: int) -> DisputeCase:
        current = await self.get(case.case_id) if self._context.role is Role.CUSTOMER else None
        if current is None:
            _customer_of(self._context)
            raise CaseNotFoundError()
        if current.version != expected_version:
            raise ConcurrencyConflictError("the case changed since it was read")
        if (case.customer_id, case.transaction_id, case.idempotency_key) != (
            current.customer_id,
            current.transaction_id,
            current.idempotency_key,
        ):
            raise ConcurrencyConflictError("a case's owner, transaction, and idempotency key cannot change")
        stored = case.evolve(version=expected_version + 1)
        self._cases.put(case.case_id, stored)
        return stored


class InMemoryConversationRepository:
    def __init__(
        self, conversations: TableView[str, Conversation], turns: TableView[str, Turn], context: AccessContext
    ) -> None:
        self._conversations = conversations
        self._turns = turns
        self._context = context

    async def get(self, conversation_id: ConversationId) -> Conversation | None:
        owner = _customer_of(self._context)
        conversation = self._conversations.get(conversation_id)
        return conversation if conversation is not None and conversation.customer_id == owner else None

    async def add(self, conversation: Conversation) -> None:
        if conversation.customer_id != _customer_of(self._context):
            raise AccessContextError("a conversation can only be added for the context customer")
        if self._conversations.get(conversation.conversation_id) is not None:
            raise DuplicateEntityError("a conversation with this id already exists")
        self._conversations.put(conversation.conversation_id, conversation)

    async def update(self, conversation: Conversation, *, expected_version: int) -> Conversation:
        current = await self.get(conversation.conversation_id)
        if current is None:
            raise ConversationNotFoundError()
        if current.version != expected_version:
            raise ConcurrencyConflictError("the conversation changed since it was read")
        if conversation.customer_id != current.customer_id:
            raise ConcurrencyConflictError("a conversation's owner cannot change")
        stored = conversation.evolve(version=expected_version + 1)
        self._conversations.put(conversation.conversation_id, stored)
        return stored

    async def append_turn(self, turn: Turn) -> None:
        if await self.get(turn.conversation_id) is None:
            raise ConversationNotFoundError()
        if self._turns.get(turn.turn_id) is not None:
            raise DuplicateEntityError("a turn with this id already exists")
        if any(t.conversation_id == turn.conversation_id and t.sequence == turn.sequence for t in self._turns.values()):
            raise DuplicateEntityError("a turn with this sequence number already exists")
        self._turns.put(turn.turn_id, turn)

    async def get_turn(self, turn_id: TurnId) -> Turn | None:
        turn = self._turns.get(turn_id)
        if turn is None or await self.get(turn.conversation_id) is None:
            return None
        return turn

    async def list_turns(self, conversation_id: ConversationId, limit: int = 100) -> Sequence[Turn]:
        if await self.get(conversation_id) is None:
            return []
        found = [turn for turn in self._turns.values() if turn.conversation_id == conversation_id]
        return sorted(found, key=lambda turn: turn.sequence)[:limit]


class InMemoryExecutionRecordRepository:
    def __init__(self, records: TableView[str, ExecutionRecord], context: AccessContext) -> None:
        self._records = records
        self._context = context

    def _reader(self) -> CustomerId | None:
        """The customer whose records are visible, or ``None`` for an evaluator, who sees every record."""
        return None if self._context.role is Role.EVALUATOR else _customer_of(self._context)

    def _visible(self, record: ExecutionRecord, reader: CustomerId | None) -> bool:
        return reader is None or record.customer_ref == reader

    async def append(self, record: ExecutionRecord) -> None:
        if record.customer_ref != _customer_of(self._context):
            raise AccessContextError("a record can only be appended for the context customer")
        existing = self._records.get(record.turn_id)
        if existing is not None:
            if existing == record:
                return
            raise AppendOnlyViolationError("a turn already has a different execution record")
        self._records.put(record.turn_id, record)

    async def get(self, turn_id: TurnId) -> ExecutionRecord | None:
        reader = self._reader()
        record = self._records.get(turn_id)
        return record if record is not None and self._visible(record, reader) else None

    async def list_for_conversation(self, conversation_id: ConversationId) -> Sequence[ExecutionRecord]:
        reader = self._reader()
        found = [r for r in self._records.values() if r.conversation_id == conversation_id and self._visible(r, reader)]
        return sorted(found, key=lambda record: (record.recorded_at, record.turn_id))

    async def count_eligibility_assessments(self, since: datetime) -> int:
        owner = _customer_of(self._context)
        return sum(
            len(record.eligibility_assessments)
            for record in self._records.values()
            if record.customer_ref == owner and record.recorded_at >= since
        )


class InMemoryHandoffRepository:
    def __init__(self, handoffs: TableView[str, HandoffRecord], context: AccessContext) -> None:
        self._handoffs = handoffs
        self._context = context

    async def add(self, handoff: Handoff) -> HandoffRecord:
        if handoff.customer_ref != _customer_of(self._context):
            raise AccessContextError("a handoff can only be added for the context customer")
        existing = self._handoffs.get(handoff.handoff_id)
        if existing is not None:
            if existing.handoff == handoff:
                return existing
            raise DuplicateEntityError("a different handoff with this id already exists")
        record = HandoffRecord(handoff=handoff)
        self._handoffs.put(handoff.handoff_id, record)
        return record

    async def get(self, handoff_id: HandoffId) -> HandoffRecord | None:
        record = self._handoffs.get(handoff_id)
        if self._context.role is Role.AGENT:
            return record
        owner = _customer_of(self._context)
        return record if record is not None and record.handoff.customer_ref == owner else None

    async def list(self, query: HandoffQuery) -> Sequence[HandoffRecord]:
        _staff_of(self._context, Role.AGENT)

        def matches(record: HandoffRecord) -> bool:
            document = record.handoff
            return (
                (not query.statuses or record.status in query.statuses)
                and (not query.priorities or document.priority in query.priorities)
                and (not query.reasons or document.escalation_reason.code in query.reasons)
                and (not query.languages or document.language in query.languages)
                and (not query.workflows or (document.workflow is not None and document.workflow.id in query.workflows))
                and (query.sla_due_before is None or document.sla_due < query.sla_due_before)
            )

        found = [record for record in self._handoffs.values() if matches(record)]
        found.sort(key=lambda record: (record.handoff.sla_due, record.handoff.handoff_id))
        return found[: query.limit]

    def _existing(self, handoff_id: HandoffId) -> HandoffRecord:
        record = self._handoffs.get(handoff_id)
        if record is None:
            raise HandoffNotFoundError()
        return record

    async def claim(self, handoff_id: HandoffId, *, at: datetime) -> HandoffRecord:
        staff_id = _staff_of(self._context, Role.AGENT)
        claimed = self._existing(handoff_id).claim(staff_id, at)
        self._handoffs.put(handoff_id, claimed)
        return claimed

    async def resolve(
        self, handoff_id: HandoffId, *, outcome: HandoffOutcomeCode, note: str, at: datetime
    ) -> HandoffRecord:
        staff_id = _staff_of(self._context, Role.AGENT)
        resolved = self._existing(handoff_id).resolve(staff_id, outcome, note, at)
        self._handoffs.put(handoff_id, resolved)
        return resolved


class InMemoryAuditLog:
    """Audit log over a table view. ``context`` may be ``None`` for the standalone log (appends only)."""

    def __init__(self, events: TableView[str, AuditEvent], context: AccessContext | None) -> None:
        self._events = events
        self._context = context

    async def append(self, event: AuditEvent) -> None:
        existing = self._events.get(event.event_id)
        if existing is not None:
            if existing == event:
                return
            raise AppendOnlyViolationError("an audit event with this id already exists")
        self._events.put(event.event_id, event)

    async def list(self, query: AuditQuery) -> Sequence[AuditEvent]:
        if self._context is None:
            raise AccessContextError("listing audit events needs an evaluator context")
        _staff_of(self._context, Role.EVALUATOR)

        def matches(event: AuditEvent) -> bool:
            return (
                (query.since is None or event.occurred_at >= query.since)
                and (query.until is None or event.occurred_at <= query.until)
                and (query.action is None or event.action == query.action)
            )

        found = [event for event in self._events.values() if matches(event)]
        found.sort(key=lambda event: (event.occurred_at, event.event_id))
        return found[: query.limit]


class InMemoryCreditProfileReader:
    def __init__(self, profiles: TableView[str, CreditProfile], context: AccessContext) -> None:
        self._profiles = profiles
        self._context = context

    async def get_mine(self) -> CreditProfile | None:
        return self._profiles.get(_customer_of(self._context))


class InMemoryCreditApplicationRepository:
    def __init__(
        self,
        applications: TableView[str, CreditApplicationIntake],
        handoffs: TableView[str, HandoffRecord],
        context: AccessContext,
    ) -> None:
        self._applications = applications
        self._handoffs = handoffs
        self._context = context

    def _own(self) -> list[CreditApplicationIntake]:
        owner = _customer_of(self._context)
        return [item for item in self._applications.values() if item.customer_id == owner]

    def _referenced_by_a_handoff(self, application_id: ApplicationId) -> bool:
        for record in self._handoffs.values():
            review = record.handoff.credit_review
            if review is not None and review.application_ref == application_id:
                return True
        return False

    def _reviewable(self, application: CreditApplicationIntake) -> bool:
        """Agents see every reviewable intake, plus any intake a handoff references."""
        return application.status in REVIEWABLE_APPLICATION_STATUSES or self._referenced_by_a_handoff(
            application.application_id
        )

    async def create(self, intake: CreditApplicationIntake) -> CreditApplicationIntake:
        if intake.customer_id != _customer_of(self._context):
            raise AccessContextError("an application can only be created for the context customer")
        existing = next((item for item in self._own() if item.idempotency_key == intake.idempotency_key), None)
        if existing is not None:
            if existing.same_request(intake):
                return existing
            raise IdempotencyConflictError()
        if self._applications.get(intake.application_id) is not None:
            raise DuplicateEntityError("an application with this id already exists")
        self._applications.put(intake.application_id, intake)
        return intake

    async def get(self, application_id: ApplicationId) -> CreditApplicationIntake | None:
        application = self._applications.get(application_id)
        if self._context.role is Role.AGENT:
            return application if application is not None and self._reviewable(application) else None
        owner = _customer_of(self._context)
        return application if application is not None and application.customer_id == owner else None

    async def list_mine(
        self, statuses: frozenset[ApplicationStatus] | None = None, limit: int = 50
    ) -> Sequence[CreditApplicationIntake]:
        found = [item for item in self._own() if statuses is None or item.status in statuses]
        found.sort(key=lambda item: item.application_id)
        found.sort(key=lambda item: item.created_at, reverse=True)
        return found[:limit]

    async def list_for_review(
        self, statuses: frozenset[ApplicationStatus] | None = None, limit: int = 50
    ) -> Sequence[CreditApplicationIntake]:
        _staff_of(self._context, Role.AGENT)
        found = [
            item
            for item in self._applications.values()
            if self._reviewable(item) and (statuses is None or item.status in statuses)
        ]
        found.sort(key=lambda item: item.application_id)
        found.sort(key=lambda item: item.created_at, reverse=True)
        return found[:limit]

    async def transition(
        self,
        application_id: ApplicationId,
        status: ApplicationStatus,
        *,
        expected_version: int,
        at: datetime,
        reason_code: str,
    ) -> CreditApplicationIntake:
        if self._context.role is Role.AGENT:
            if status not in REVIEWER_APPLICATION_TRANSITIONS:
                raise AccessContextError("an agent can only take an application into review or close it")
        else:
            _customer_of(self._context)
            if status not in CUSTOMER_APPLICATION_TRANSITIONS:
                raise AccessContextError("a customer can only withdraw an application")
        current = await self.get(application_id)
        if current is None:
            raise CreditApplicationNotFoundError()
        if current.version != expected_version:
            raise ConcurrencyConflictError("the application changed since it was read")
        moved = current.transition_to(status, at=at, reason_code=reason_code).evolve(version=expected_version + 1)
        self._applications.put(application_id, moved)
        return moved


class InMemoryActionLedger:
    def __init__(self, entries: TableView[tuple[str, str, str], ActionLedgerEntry], context: AccessContext) -> None:
        self._entries = entries
        self._context = context

    async def find(self, action: ActionKind, key: IdempotencyKey) -> ActionLedgerEntry | None:
        return self._entries.get((_customer_of(self._context), action.value, key))

    async def record(self, entry: ActionLedgerEntry) -> ActionLedgerEntry:
        slot = (_customer_of(self._context), entry.action.value, entry.idempotency_key)
        existing = self._entries.get(slot)
        if existing is not None:
            if existing.request_digest != entry.request_digest:
                raise IdempotencyConflictError()
            return existing
        self._entries.put(slot, entry)
        return entry
