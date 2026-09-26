# bank_agent.domain

## Responsibility

The domain layer holds the business vocabulary of the dispute workflow: value objects, entities, the trust state, workflow concepts, the handoff and execution record contracts, and typed domain errors. It is pure. It performs no I/O, reads no configuration, and imports no framework, database, HTTP, or model library.

[docs/architecture/domain-model.md](../../../../../docs/architecture/domain-model.md) has the class diagram, the case lifecycle, the trust tier rules, and the personal-data tables.

## Public interfaces

| Module | Main types |
|---|---|
| `base.py` | `DomainModel`, `Pii`, `Internal`, `pii_fields`, `internal_fields`, `UtcDatetime`, `UntrustedText` |
| `money.py` | `Currency`, `Money` (exact Decimal arithmetic, banker's rounding on request), `ExchangeRate` |
| `identifiers.py` | `CustomerId`, `ProductId`, `TransactionId`, `CaseId`, `ConversationId`, `TurnId`, `SessionId`, `LineageId`, `HandoffId`, and more; `SourceRef` |
| `access.py` | `AuthLevel`, `Role`, `Channel`, `AccessContext` |
| `customer.py`, `product.py`, `transaction.py`, `complaint.py`, `dispute.py` | Banking entities and the case lifecycle |
| `session.py`, `identity.py`, `trust.py` | Sessions, identity challenges, append-only trust state |
| `workflow.py`, `intelligence.py`, `decision.py`, `actions.py`, `policy.py` | Workflow and policy vocabulary |
| `conversation.py` | Conversations, turns, `AssistantResponse`, `TurnResult` |
| `handoff.py`, `execution_record.py`, `audit.py` | Contract documents and audit events |
| `errors.py` | The error taxonomy |

## Conventions

- Models are frozen and reject unknown keys. Change an entity with `evolve(...)` (which revalidates) or a named method, never `model_copy(update=...)`.
- Identifiers are `NewType` aliases wrapped in `Annotated` constraints: `CustomerId("C1")` is a plain string at runtime, and mypy keeps kinds apart.
- Money is `Decimal` with an explicit currency; floats are rejected. Rounding happens only in `Money.rounded()`.
- Times are timezone-aware and normalized to UTC; the current time comes from the `Clock` port, identifiers from the `IdGenerator` port.
- Mark personal data with `Pii(kind)` and customer-invisible data with `Internal()` in the field's `Annotated` metadata.
- Customer and record text is `UntrustedText`.
- Constructor failures surface as Pydantic `ValidationError` (validators raise `ValueError`); behavioral failures raise a `DomainError` subclass with a stable code.

## Who may import it

Every other layer, and `bank_evals`. It imports nothing from `bank_agent` except other `domain` modules. import-linter enforces this with the layers contract and the pure-core contract.

## How to extend

- Add an entity or value object as a `DomainModel` subclass, with invariants in validators.
- Add a typed error as a subclass of the right family in `errors.py` with a unique snake-case `code`; `bank_agent/api/domain_problems.py` maps the families.
- Changing `Handoff`, `ExecutionRecord`, `Decision`, or `ClauseMetadata` changes a published contract: follow `contracts/README.md` and run `make contracts`.

## How to test

Unit tests under `services/api/tests/unit/domain/`, with Hypothesis property tests for money arithmetic, trust-tier monotonicity, and the case lifecycle. Builders for valid objects live in `services/api/tests/bank_agent_builders.py`. Coverage gate: 90% line coverage.
