# 0010: Idempotency keys and read-back verification for writes

- Status: accepted
- Date: 2026-09-27

## Context

The system may report only actions whose outcome it has verified (brief and CLAUDE.md section 1). Writes cross process and network boundaries: a timeout after a commit, a retried request, or a model that repeats itself can each cause a second attempt. The three writes (open a dispute case, block a card, record a credit application intake) must never happen twice, and the workflow must never say "done" when the record does not exist.

## Considered options

1. **Trust the return value of the write.** Simple, but a failure between the write and the answer, or a partial write, is reported as success.
2. **Idempotency keys only.** Repeats are safe, but a write that silently did not commit is still reported as done.
3. **Idempotency keys plus a read-back** in a fresh unit of work that must find the expected state before anything is reported.

## Decision

Option 3:

- Every write tool takes an idempotency key chosen by the workflow when the customer confirms, so a retry of the same confirmation reuses it.
- Dispute cases and credit applications store the key in a column that is unique per customer. A repeated key with the same request returns the stored record; with a different request it raises `IdempotencyConflictError`.
- A card block changes a product row that has no key column, so the `ActionLedger` port records the first outcome per customer, action, and key (`action_idempotency`); the same key replays that outcome, and a different request with the key conflicts.
- `WriteVerifier` reads each write back in a new unit of work: the case exists with the expected transaction and reason and is open; the product is `blocked`; the application exists with the expected product, amount, and term and is `submitted`. It returns a `Verification` with an evidence reference (`table:id`) or a mismatch code.
- `ToolFailureInjector` can make a write run in a unit of work that never commits (partial write), so tests and evaluations prove that verification catches it. The composition root refuses it in production.
- The audit event of a write is appended in the same unit of work as the write, so a committed write always has its audit event and a rolled-back one never does.

## Consequences

- A write costs one extra read; negligible next to a model call.
- The workflow (phase 09) must generate one key per confirmation and keep it across retries, and must treat a failed verification as "not done" (clarify, retry, or hand off).
- Keys are per customer, so two customers can never collide, and a key can never be used to probe another customer's records.
- The ledger adds a table and a port that the memory and PostgreSQL adapters both implement and a contract suite covers.
