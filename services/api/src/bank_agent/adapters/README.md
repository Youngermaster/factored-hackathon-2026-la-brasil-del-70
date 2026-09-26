# bank_agent.adapters

## Responsibility

Adapters implement ports with real technology: PostgreSQL and DuckDB persistence, in-memory implementations for tests, the language model gateway, retrieval, identity, model loading, and telemetry. They translate between external representations and domain objects, so nothing outside this package sees an ORM row or a provider payload.

## Layout

```text
adapters/
└── persistence/
    └── postgres/
        └── readiness.py   PostgresReadinessCheck: SELECT 1 as the application role
```

Later phases add `persistence/{postgres,duckdb,memory}` repositories, `llm/`, `retrieval/`, `identity/`, `models/`, and `telemetry/`.

## Who may import it

`api` and `bootstrap` only; in practice only `bootstrap/container.py` constructs adapters. Adapters may import `application`, `policy`, `ports`, and `domain`.

## How to extend

1. Implement the port's Protocol in `adapters/<area>/<technology>/`.
2. Add the adapter to the port's shared contract suite in `services/api/tests/contracts/`.
3. Select it by name in `bootstrap/container.py`, driven by settings.
4. Customer data access sets the PostgreSQL row-level security context inside each transaction and connects as the application role, which owns no tables and has no `BYPASSRLS`.

## How to test

Integration tests against real PostgreSQL through testcontainers (`services/api/tests/integration/`), and the shared contract suites. Coverage gate: 80% line coverage.
