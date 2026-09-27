# bank_agent.application

## Responsibility

The application layer orchestrates: the workflow engine, the dispute intake and status workflows, the protective card block, handoffs, and execution records. It calls ports, asks the policy kernel for decisions, and reports only outcomes it has verified. It never knows which adapter sits behind a port.

Phase 09 builds the workflow engine. Phase 05 added two use-case packages:

- `identity/`: `SessionService` (login, step-up with session rotation, resolution with idle and absolute expiry, logout, revocation) over the `IdentityProvider` and `SessionStore` ports, and `policy.py` with the fixed lifetimes (`docs/security/identity-and-sessions.md`).
- `tools/`: the banking tools, the only operations a workflow may use. `BankingTools.for_session(SessionContext)` returns `SessionTools` (reads for all four workflows and the three idempotent writes); `engine_only()` returns the credit profile read that no allowlist may reach; `WriteVerifier` reads every write back into a `Verification`; `ToolFailureInjector` injects timeouts, transient and permanent errors, and partial writes for tests and evaluations and is refused in production. Every call appends an audit event with redacted arguments in the same unit of work as its writes. The tools hold no policy defaults: `ToolPolicy.from_policy` takes the statement period cap (`ACC-ALL-2`), the dispute resolution target per country (`DSP-<country>-2`), and the writes that need step-up (`policies/matrix.yaml`; all three) from the policy pack.

## Who may import it

`adapters`, `api`, and `bootstrap`. The application layer imports `policy`, `ports`, and `domain` only.

## How to extend

- Add a use case as a class or function that receives its ports as constructor or call arguments, never as globals.
- Add a workflow state with its bound rules, bound clauses, and per-state tool allowlist; tools never accept customer identifiers from the model.
- Time comes from the `Clock` port and identifiers from the `IdGenerator` port, so tests can freeze both.
- Add a tool as a `ToolCalls` method that does its work inside `_run` (one unit of work, one audit event), add it to `SessionToolset` and the failure injector, add its `ToolName`, and cover it in the tool contract suites (`tests/contracts/test_read_tools_contract.py`, `test_write_tools_contract.py`) so it runs on the memory and PostgreSQL backends. A write also needs an idempotency rule and a `WriteVerifier` read-back.

## How to test

Unit tests with in-memory adapters, `FakeLLM`, `FixedClock`, and deterministic id generators; scenario-style integration tests for full workflows. Coverage gate: 90% line coverage.
