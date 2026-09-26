# bank_agent.adapters

## Responsibility

Adapters implement ports with real technology: PostgreSQL and DuckDB persistence, in-memory implementations for tests, the language model gateway, retrieval, identity, model loading, and telemetry. They translate between external representations and domain objects, so nothing outside this package sees an ORM row or a provider payload.

## Layout

```text
adapters/
├── persistence/
│   ├── memory/
│   │   ├── store.py          InMemoryStore (committed tables) and transactional table views
│   │   ├── repositories.py   every repository port, bound to an AccessContext
│   │   ├── unit_of_work.py   InMemoryUnitOfWork(Factory): staged writes, atomic commit, conflict detection
│   │   └── sessions.py       InMemorySessionStore with trust state per lineage
│   └── postgres/
│       └── readiness.py      PostgresReadinessCheck: SELECT 1 as the application role
├── system/
│   ├── clock.py              SystemClock: UTC, never goes backwards within a process
│   └── ids.py                RandomIdGenerator: kind prefix plus 128 random bits
└── telemetry/
    └── noop.py               NoopTelemetry until the OpenTelemetry adapter (phase 15)
```

The memory adapters enforce the same access rules, append-only rules, idempotency, and optimistic concurrency the PostgreSQL adapters must provide, and pass the same contract suites. Their unit of work stages writes per table and applies them on `commit`; a commit that touches a key another unit of work changed in the meantime raises `ConcurrencyConflictError` and applies nothing. `InMemoryStore.seed` bypasses access contexts and exists for tests, fixtures, and demos only.

Later phases add `persistence/duckdb` (phase 03, readers only), `persistence/postgres` repositories (phase 05), `identity/` (phase 05), `policy/` (phase 06), `retrieval/` (phase 07), `llm/` (phase 08), `models/` (phases 09 and 10), and an OpenTelemetry adapter (phase 15). `docs/architecture/ports-and-adapters.md` has the full table.

## Who may import it

`api` and `bootstrap` only; in practice only `bootstrap/container.py` constructs adapters. Adapters may import `application`, `policy`, `ports`, and `domain`.

## How to extend

1. Implement the port's Protocol in `adapters/<area>/<technology>/`.
2. Add a backend to `READ_BACKENDS` or `WRITE_BACKENDS` in `services/api/tests/bank_agent_contracts.py` (marked `integration` when it needs a database), so the port's shared contract suite in `services/api/tests/contracts/` runs against it.
3. Select it by name in `bootstrap/container.py`, driven by settings.
4. Customer data access sets the PostgreSQL row-level security context inside each transaction and connects as the application role, which owns no tables and has no `BYPASSRLS`.

## How to test

Integration tests against real PostgreSQL through testcontainers (`services/api/tests/integration/`), and the shared contract suites. Coverage gate: 80% line coverage.
