# bank_agent.application

## Responsibility

The application layer orchestrates: the workflow engine, the dispute intake and status workflows, the protective card block, handoffs, and execution records. It calls ports, asks the policy kernel for decisions, and reports only outcomes it has verified. It never knows which adapter sits behind a port.

Phase 09 builds the workflow engine; phase 05 and later add use cases.

## Who may import it

`adapters`, `api`, and `bootstrap`. The application layer imports `policy`, `ports`, and `domain` only.

## How to extend

- Add a use case as a class or function that receives its ports as constructor or call arguments, never as globals.
- Add a workflow state with its bound rules, bound clauses, and per-state tool allowlist; tools never accept customer identifiers from the model.
- Time comes from the `Clock` port and identifiers from the `IdGenerator` port, so tests can freeze both.

## How to test

Unit tests with in-memory adapters, `FakeLLM`, `FixedClock`, and deterministic id generators; scenario-style integration tests for full workflows. Coverage gate: 90% line coverage.
