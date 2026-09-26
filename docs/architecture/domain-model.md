# Domain model

The domain layer (`services/api/src/bank_agent/domain`) holds the vocabulary of the dispute workflow: value objects, entities, the trust state, workflow concepts, the handoff and execution record contracts, and the error taxonomy. It is pure: no I/O, no framework, no configuration. Every model is an immutable Pydantic model that rejects unknown keys; entities change by returning a validated copy (`evolve`, or a named method such as `transition_to`).

Approved at the phase 02 checkpoint on 2026-09-26. See [the phase 02 plan](../plans/phase-02.md) for the reasoning behind each field that later phases need.

## Class diagram

```mermaid
classDiagram
    direction LR
    class Money {
        +Decimal amount
        +Currency currency
        +add(other) Money
        +rounded() Money
    }
    class ExchangeRate {
        +Currency source
        +Currency target
        +Decimal rate
        +convert(money) Money
    }
    class Customer {
        +CustomerId customer_id
        +Country country
        +CustomerSegment segment
        +PiiText first_name
    }
    class Product {
        +ProductId product_id
        +ProductType product_type
        +ProductStatus status
        +MaskedNumber masked_number
        +blocked() Product
    }
    class Transaction {
        +TransactionId transaction_id
        +datetime occurred_at
        +Money amount
        +UntrustedText merchant_name
        +TransactionStatus status
        +FraudContext fraud
    }
    class DisputeCase {
        +CaseId case_id
        +DisputeReason reason
        +DisputeStatus status
        +IdempotencyKey idempotency_key
        +datetime sla_due_at
        +transition_to(status) DisputeCase
    }
    class HistoricalComplaint {
        +ComplaintId complaint_id
        +datetime created_at
        +Priority priority
    }
    class Session {
        +SessionId session_id
        +LineageId lineage_id
        +Role role
        +AuthLevel auth_level
        +expiry_reason(now) ExpiryReason
        +snapshot(now) SessionSnapshot
    }
    class TrustState {
        +LineageId lineage_id
        +append(event) TrustState
        +risk_tier() RiskTier
    }
    class TrustEvent {
        +TrustEventKind kind
        +datetime occurred_at
        +str detail_code
    }
    class Conversation {
        +ConversationId conversation_id
        +WorkflowPosition position
        +int version
    }
    class Turn {
        +TurnId turn_id
        +UntrustedText customer_text
        +AssistantResponse response
    }
    class ExecutionRecord {
        +str state_before
        +str state_after
        +Outcome outcome
        +str policy_pack_version
        +Decimal cost_usd
    }
    class Decision {
        +DecisionKind kind
        +str policy_pack_version
    }
    class RuleResult {
        +str rule_id
        +int rule_version
        +bool passed
        +str reason_code
    }
    class ClauseRef {
        +str clause_id
        +int version
    }
    class ToolCallRecord {
        +ToolName tool
        +ToolCallStatus status
    }
    class Verification {
        +bool verified
        +SourceRef evidence
    }
    class Handoff {
        +CustomerId customer_ref
        +EscalationReason escalation_reason
        +Priority priority
        +datetime sla_due
    }
    class VerifiedFact {
        +str fact
        +SourceRef source
    }
    class ActionTaken {
        +ActionKind action
        +VerificationStatus verification
        +SourceRef evidence
    }
    class HandoffRecord {
        +HandoffStatus status
        +claim(staff, at) HandoffRecord
        +resolve(staff, outcome, note, at) HandoffRecord
    }
    Customer "1" --> "*" Product : owns
    Product "1" --> "*" Transaction : records
    Customer "1" --> "*" DisputeCase : files
    Customer "1" --> "*" HistoricalComplaint : filed
    DisputeCase --> Transaction : disputes
    Transaction --> Money
    Session --> TrustState : lineage
    TrustState "1" *-- "*" TrustEvent
    Conversation "1" *-- "*" Turn
    Turn "1" --> "1" ExecutionRecord : audited by
    ExecutionRecord *-- Decision
    Decision *-- RuleResult
    RuleResult --> ClauseRef
    ExecutionRecord *-- ToolCallRecord
    ToolCallRecord --> Verification
    HandoffRecord *-- Handoff
    Handoff *-- VerifiedFact
    Handoff *-- ActionTaken
    Handoff --> ClauseRef : policy basis
```

## Modules

| Module | Contents |
|---|---|
| `base.py` | `DomainModel` (frozen, extra keys forbidden, `evolve`), the `Pii` and `Internal` markers with `pii_fields` and `internal_fields`, `UtcDatetime`, `UntrustedText`, `Code`, `SingleLineText`, `SummaryText` |
| `errors.py` | The error taxonomy with stable codes (see below) |
| `money.py` | `Currency`, `Money`, `ExchangeRate` ([ADR 0004](../adr/0004-money-and-currency-handling.md)) |
| `locale.py` | `Country`, `CountryCode`, `Language`, `Locale` |
| `identifiers.py` | Typed identifiers (`CustomerId`, `CaseId`, `TurnId`, and so on), `IdKind`, `SourceRef` (`table:id`) |
| `masking.py` | `MaskedNumber` (last four characters only) |
| `access.py` | `AuthLevel`, `Role`, `Channel`, `AccessContext` |
| `customer.py`, `product.py`, `transaction.py`, `complaint.py` | Banking entities |
| `dispute.py` | `DisputeReason`, `DisputeStatus`, `DisputeCase` and its lifecycle |
| `session.py`, `identity.py` | Sessions, session snapshots, token digests, identification, one-time-code challenges |
| `trust.py` | `TrustEvent`, `TrustState`, `RiskTier` ([ADR 0005](../adr/0005-trust-state-append-only.md)) |
| `workflow.py` | `StateName`, `Intent`, `Outcome`, `WorkflowRef` |
| `intelligence.py` | Model and prompt references, intent predictions, transaction descriptors and resolutions, language detection, retrieval, model artifacts, language model results |
| `decision.py` | `DecisionKind`, `ClauseRef`, `RuleResult`, `Decision` |
| `actions.py` | `ActionKind`, `ToolName`, `ToolFailureMode`, `ActionRequest`, `ActionResult`, `Verification` |
| `policy.py` | `ClauseMetadata`, `PolicyClause`, `ActionRequirement` |
| `conversation.py` | `Conversation`, `WorkflowPosition`, `Turn`, `AssistantResponse` and its parts, `TurnResult` |
| `handoff.py` | `Handoff` version 1 and `HandoffRecord` ([ADR 0006](../adr/0006-handoff-and-execution-record-contracts.md)) |
| `execution_record.py` | `ExecutionRecord` version 1 |
| `audit.py` | `AuditEvent` |

## Dispute case lifecycle

```mermaid
stateDiagram-v2
    [*] --> opened
    opened --> in_review
    opened --> escalated
    opened --> rejected
    in_review --> resolved
    in_review --> rejected
    in_review --> escalated
    escalated --> in_review
    escalated --> resolved
    escalated --> rejected
    resolved --> [*]
    rejected --> [*]
```

Self-transitions and any transition out of `resolved` or `rejected` raise `InvalidCaseTransitionError`, and a change dated before the last update is refused. There is no `opened` to `resolved` shortcut. `DisputeCase.open` copies the customer, product, and amount from the transaction, so a case cannot point at another customer's transaction.

## Handoff lifecycle

A `Handoff` document never changes after it is stored. Its `HandoffRecord` moves from `open` to `claimed` (by one agent) to `resolved` (by the same agent, with an outcome code and a note).

## Trust state

| Severity | Event kinds |
|---|---|
| Low | `failed_otp`, `unusual_amount` |
| Medium | `otp_lockout`, `injection_detected`, `third_party_admission` |
| High | `cross_customer_probe`, `identity_mismatch` |

The risk tier is the highest reached by these rules: one medium event gives `elevated`; one high event gives `high`; two medium-or-higher events give `high`; three low events give `elevated`. The tier never decreases as events are appended, and the state is keyed by the session lineage, which survives rotation and re-authentication into the same conversation.

## Personal and internal data

| Model | Field | Marker |
|---|---|---|
| `Customer` | `first_name` | `Pii("name")` |
| `Turn` | `customer_text` | `Pii("free_text")` |
| `DocumentIdentification` | `document_number`, `phone_last4` | `Pii("document_number")`, `Pii("phone")`; hidden from `repr` |
| `OtpDispatch`, `OtpDeliveryReceipt` | `code`, `demo_code` | `Pii("credential")`; hidden from `repr` |
| `HandoffResolution` | `note` | `Pii("free_text")` |
| `Transaction` | `fraud` (label and score) | `Internal()`; hidden from `repr`, never rendered or sent to a model |

Document numbers, phones, emails, birth dates, and addresses never enter the domain `Customer`. Customer and record text travels as `UntrustedText`, which prompt builders must wrap as data.

## Error taxonomy

Every error has a stable snake-case `code` and a `retryable` flag, and its message never contains personal data. `bank_agent/api/domain_problems.py` maps the families to problem types:

| Family | Status | Examples |
|---|---|---|
| `NotFoundError` | 404 | `case_not_found`; another customer's resource raises the same error |
| `AuthenticationError` | 401 | `session_expired` (own problem type), `identity_challenge_failed` (deliberately generic), `identity_locked` |
| `AuthorizationError` | 403 (500 for `access_context_invalid`) | `step_up_required` (own problem type), `auth_level_insufficient` |
| `ConflictError` | 409 | `idempotency_key_conflict`, `concurrency_conflict`, `append_only_violation` |
| `StateTransitionError` | 409 | `case_transition_invalid`, `product_state_invalid` |
| `InvariantViolationError` | 422 | `currency_mismatch`, `money_precision_exceeded`, `trust_state_append_only` |
| `DependencyError` | 503 | the LLM, tool, and model artifact errors |
| `ConfigurationError` | 500 | `prompt_not_found`, `policy_binding_missing` |

## Contracts

The handoff, execution record, decision, scenario, and policy clause models are published as JSON Schemas in [`contracts/schemas/`](../../contracts/README.md), generated by `make contracts`, with a test that fails when they are stale.
