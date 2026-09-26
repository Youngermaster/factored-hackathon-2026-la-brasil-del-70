# bank_agent.ports

## Responsibility

Ports are the `typing.Protocol` interfaces through which the application reaches the outside world: repositories for each aggregate, the clock and id generator, the language model client, the intent router, the transaction resolver, the retriever, the model registry, and health checks. They describe behavior in domain terms and return domain objects, never ORM rows, dataframes, or HTTP payloads.

## Current ports

| Module | Port | Purpose |
|---|---|---|
| `health.py` | `ReadinessCheck` | One dependency checked by `/health/ready`; returns a boolean and never raises for an unavailable dependency |

Phase 02 adds the domain ports.

## Who may import it

`policy`, `application`, `adapters`, `api`, and `bootstrap`. Ports import only `domain` and the standard library, and the pure-core contract forbids framework and I/O libraries here.

## How to extend

1. Add a Protocol in a module named after the capability. Document the behavior every implementation must guarantee, including error behavior.
2. Add a shared contract suite in `services/api/tests/contracts/`: one parameterized test class that every adapter for the port must pass.
3. Implement adapters under `adapters/` and select them in `bootstrap/container.py`.
4. For cross-cutting behavior (retry, timeout, tracing, redaction), write a decorator that implements the same Protocol and wraps another implementation.

## How to test

Ports have no behavior of their own; the contract suites test their implementations. Coverage gate: 90% line coverage.
