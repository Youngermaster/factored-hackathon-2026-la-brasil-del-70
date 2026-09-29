# bank_agent.ports

## Responsibility

Ports are the `typing.Protocol` interfaces through which the application reaches the outside world. They describe behavior in domain terms and exchange domain objects, never ORM rows, dataframes, or HTTP payloads. Every port docstring states its preconditions, postconditions, error behavior, and the isolation guarantee an implementation must uphold.

## Current ports

| Module | Port | Mode | Purpose |
|---|---|---|---|
| `repositories/customers.py` | `CustomerReader`, `CustomerRepository` | async | The bound customer's profile |
| `repositories/products.py` | `ProductReader`, `ProductRepository` | async | Products; compare-and-set status change for a card block |
| `repositories/transactions.py` | `TransactionReader`, `TransactionRepository`, `TransactionQuery` | async | Read-only transactions, newest first |
| `repositories/complaints.py` | `HistoricalComplaintReader`, `HistoricalComplaintRepository` | async | Intake-time complaint history |
| `repositories/cases.py` | `CaseRepository` | async | Dispute cases with idempotent creation and optimistic versions |
| `repositories/credit_profiles.py` | `CreditProfileReader` | async | The bound customer's credit profile (customer role only) |
| `repositories/credit_applications.py` | `CreditApplicationRepository` | async | Credit application intakes for human review, idempotent, with optimistic versions |
| `repositories/conversations.py` | `ConversationRepository` | async | Conversations and turns |
| `repositories/execution_records.py` | `ExecutionRecordRepository` | async | Append-only execution records |
| `repositories/handoffs.py` | `HandoffRepository`, `HandoffQuery` | async | Handoffs and the agent inbox lifecycle |
| `audit.py` | `AuditLog`, `AuditQuery` | async | Append-only audit events, inside or outside a unit of work |
| `unit_of_work.py` | `UnitOfWork`, `UnitOfWorkFactory` | async | One transaction bound to one `AccessContext`, exposing every repository |
| `sessions.py` | `SessionStore` | async | Sessions by token digest, and trust state by lineage |
| `identity.py` | `IdentityProvider`, `OtpSender` | async | One-time-code identity verification |
| `determinism.py` | `Clock`, `IdGenerator` | sync | Time and identifiers |
| `llm.py` | `LLMClient` | async | Structured and text generation from versioned prompts |
| `prompts.py` | `PromptRegistry` | sync | Prompt files by id and version |
| `policy.py` | `PolicyRepository` | sync | Clauses, bindings per workflow and state, action matrix, pack version |
| `credit_catalog.py` | `CreditProductCatalog` | sync | The synthetic credit catalog (public, not customer-scoped) |
| `eligibility.py` | `EligibilityPolicy`, `EligibilityRequest` | sync | The synthetic eligibility service: indicative outcomes from `ELG` rules, never an approval |
| `retrieval.py` | `Retriever` | sync | Open retrieval over clauses |
| `models.py` | `IntentRouter`, `TransactionResolver`, `LanguageDetector`, `ModelRegistry`, `RiskEstimator` | sync | Replaceable learned or rule-based components; the risk estimator is predictive only and internal |
| `telemetry.py` | `Telemetry`, `Span`, `Counter`, `Histogram`, `Gauge` | sync | Spans, metrics, and the current trace id without importing OpenTelemetry |
| `reliability.py` | `DegradationSource` | sync | The current degradation level (L0 to L4) for the engine and the health endpoint |
| `budget.py` | `BudgetLedger` | async | Model spend per lineage, conversation, and day, shared by processes; atomic reservations |
| `health.py` | `ReadinessCheck` | async | One dependency checked by `/health/ready` |
| `evaluation.py` | `EvaluationSummaryReader` | async | Published evaluation summaries, newest first |

Async ports may perform I/O. Sync ports run in process on data loaded at startup; a remote implementation would need an async variant of the port.

`docs/architecture/ports-and-adapters.md` lists each port's present and planned adapters and the phase that adds them.

## Isolation by construction

Repositories are bound to an `AccessContext` when a unit of work creates them, and no repository method accepts a customer identifier. Another customer's resource behaves exactly like a missing one. The read side of each customer-data repository is its own Protocol (`...Reader`) so that read-only backends such as the phase 03 DuckDB adapters can implement it without a unit of work.

## Who may import it

`policy`, `application`, `adapters`, `api`, `bootstrap`, and `bank_agent.testing`. Ports import only `domain`, Pydantic, and the standard library; the pure-core contract forbids framework and I/O libraries here.

## How to extend

1. Add a Protocol in a module named after the capability, with a docstring covering preconditions, postconditions, errors, and isolation.
2. Add a shared contract suite in `services/api/tests/contracts/`: one parameterized class that every adapter for the port must pass.
3. Implement adapters under `adapters/` and select them in `bootstrap/container.py`.
4. For cross-cutting behavior (retry, timeout, tracing, redaction), write a decorator that implements the same Protocol and wraps another implementation.

## How to test

Ports have no behavior of their own; the contract suites in `services/api/tests/contracts/` test their implementations. Coverage gate: 90% line coverage.
