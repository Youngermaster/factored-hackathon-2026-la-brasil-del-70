# bank_agent.adapters

## Responsibility

Adapters implement ports with real technology: PostgreSQL and DuckDB persistence, in-memory implementations for tests, the language model gateway, retrieval, identity, model loading, and telemetry. They translate between external representations and domain objects, so nothing outside this package sees an ORM row or a provider payload.

## Layout

```text
adapters/
├── persistence/
│   ├── memory/
│   │   ├── store.py          InMemoryStore (committed tables) and transactional table views
│   │   ├── repositories.py   every repository port, bound to an AccessContext (credit profiles and
│   │   │                     applications included)
│   │   ├── unit_of_work.py   InMemoryUnitOfWork(Factory): staged writes, atomic commit, conflict detection
│   │   ├── credit_catalog.py InMemoryCreditProductCatalog, loaded from given entries
│   │   └── sessions.py       InMemorySessionStore with trust state per lineage
│   ├── duckdb/
│   │   ├── gold.py           GOLD_SCHEMAS (the serving contract), open_gold, DATASET_CREDIT_BALANCE_CONVENTION
│   │   └── readers.py        customer, product, transaction, complaint, credit profile readers; DuckDbGoldStore
│   └── postgres/
│       ├── database.py       engine creation, DatabaseRole, open_transaction (context set before anything else)
│       ├── transaction.py    Tx: bound statements, savepoints, NOWAIT locks that mark a conflict
│       ├── unit_of_work.py   PostgresUnitOfWork(Factory): SET LOCAL app.role and app.customer_id per transaction
│       ├── repositories/     one module per aggregate, bound to a Tx and its AccessContext
│       ├── mappers/          rows to domain objects and back; canonical JSON documents and content digests
│       ├── sessions.py       PostgresSessionStore and trust events (identity database role)
│       ├── challenges.py     PostgresChallengeStore for the mock identity provider
│       ├── audit.py          PostgresStandaloneAuditLog for events outside a customer transaction
│       ├── seed.py           PostgresSeeder: idempotent upserts as the owner with app.role = 'seed'
│       ├── migrate.py        programmatic Alembic upgrade and downgrade as the owner role
│       ├── migrations/       Alembic revisions 0001 to 0008 (schema, RLS, grants, append-only triggers)
│       └── readiness.py      PostgresReadinessCheck: SELECT 1 as the application role
├── identity/
│   ├── codes.py              IdentityKeys (HMAC keys derived from SESSION_SECRET), code generation and hashing
│   ├── store.py              ChallengeStore protocol, Subject, ChallengeRecord, InMemoryChallengeStore
│   ├── provider.py           MockIdentityProvider: persona or document identification, OTP, step-up
│   └── sender.py             DemoOtpSender: the code in the receipt only with DEMO_MODE=true
├── llm/
│   ├── request.py            LlmRequest and LlmDecorator, the base every decorator shares
│   ├── client.py             PromptedLLMClient: rendering, language directive, JSON Schema, one repair
│   ├── litellm_client.py     LiteLLMCompletion and LiteLLMClient (optional litellm extra, lazy import)
│   ├── cassette.py           CassetteLLM: record and replay, redacted, fails loudly when missing
│   ├── unconfigured.py       UnconfiguredLLMClient: refuses every call when no provider is set
│   ├── redaction.py          Redactor, RedactionDecorator, UNREDACTED_VARIABLE_KEYS
│   ├── budget.py             BudgetGuardDecorator, BudgetLimits, InMemoryBudgetLedger
│   ├── prices.py             PriceTable over services/api/config/llm_prices.yaml
│   ├── cost.py               CostAccountingDecorator
│   ├── tracing.py            TracingDecorator (GenAI semantic conventions 1.37.0)
│   ├── fallback.py           FallbackDecorator
│   ├── circuit_breaker.py    CircuitBreakerDecorator
│   ├── retry.py              BoundedRetryDecorator
│   └── timeout.py            TimeoutDecorator
├── models/
│   ├── keyword_router.py     router:keyword@1, weighted keyword patterns in es, pt, en (IntentRouter)
│   ├── rules_resolver.py     resolver:rules@1, amount, merchant, date, and channel evidence (TransactionResolver)
│   ├── lexical_language.py   language_detector:lexical@1, marker words and orthography (LanguageDetector)
│   ├── score_band_risk.py    risk_estimator:score_band@1, the credit risk baseline (RiskEstimator)
│   ├── registry.py           FilesystemModelRegistry (ModelRegistry) and FilesystemModelStore: JSON artifacts, digests, aliases
│   ├── tfidf_router.py       router:tfidf, TF-IDF logistic regression evaluated in pure Python (IntentRouter)
│   ├── embedding_router.py   router:embeddings, a logistic head over the ml extra's embedder (IntentRouter)
│   ├── lgbm_resolver.py      resolver:lgbm, LightGBM trees with an evidence gate and a none option (TransactionResolver)
│   ├── learned_risk.py       risk_estimator:logreg and risk_estimator:lgbm, snapshot risk estimates (RiskEstimator)
│   ├── risk_artifact.py      the risk_classifier/1 artifact: scorer, calibrator, interval, policy cut points, ranges
│   ├── risk_features.py      the risk feature vector shared with bank-ml training
│   ├── tree_ensemble.py      pure-Python evaluator for exported LightGBM trees
│   ├── text_features.py      the router analyzer shared with bank-ml training
│   └── resolver_features.py  candidate features and the evidence gate shared with bank-ml training
├── retrieval/                corpus from the pack (no ELG), BM25, dense, hybrid, embedding cache, index store
├── evaluation/
│   └── summaries.py          FilesystemEvaluationSummaries: published evaluation summaries (EvaluationSummaryReader)
├── prompts/
│   └── file_registry.py      FilePromptRegistry: versioned prompt files, variable validation, data delimiters
├── system/
│   ├── clock.py              SystemClock: UTC, never goes backwards within a process
│   └── ids.py                RandomIdGenerator: kind prefix plus 128 random bits
└── telemetry/
    └── noop.py               NoopTelemetry until the OpenTelemetry adapter (phase 15)
```

The memory adapters enforce the same access rules, append-only rules, idempotency, and optimistic concurrency the PostgreSQL adapters must provide, and pass the same contract suites. Their unit of work stages writes per table and applies them on `commit`; a commit that touches a key another unit of work changed in the meantime raises `ConcurrencyConflictError` and applies nothing. `InMemoryStore.seed` bypasses access contexts and exists for tests, fixtures, and demos only.

The DuckDB readers (phase 03) read the gold serving Parquet that `bank-data build` writes, bound to an access context with bound parameters only, and pass the read contract suites.

The PostgreSQL adapters (phase 05) pass every read and write contract suite. A unit of work opens a connection, begins a transaction, and sets `app.role` and `app.customer_id` with `set_config(..., true)` before any other statement; row-level security then filters every table again behind the repositories' own `WHERE customer_id = ...` clauses (`docs/security/data-isolation.md`). Writes lock rows with `FOR NO KEY UPDATE NOWAIT`: when another open unit of work holds the row, the unit of work is marked conflicted and `commit` raises `ConcurrencyConflictError`, the same optimistic behavior as the memory adapter, without making a request wait on another request's lock. Aggregates with nested structure store their validated domain document as JSONB next to the scalar columns used by queries and policies, and check constraints keep the two in agreement.

`policy/` (phase 06) reads the synthetic policy pack: `FilesystemPolicyRepository` implements `PolicyRepository`, `FilesystemCreditCatalog` implements `CreditProductCatalog` (with es, pt, and en display text), and `tasks.py` rewrites the version lock and the policy catalog page; the parsing and validation are the pure loader in `bank_agent.policy.loader`. `retrieval/` (phase 07) implements the `Retriever` port over the pack: BM25, dense embeddings from the optional `ml` extra, reciprocal rank fusion, and indexes keyed by the pack version ([README](retrieval/README.md)). `models/` holds the rule baselines behind the router, resolver, language detector, and risk estimator ports (phase 09), and the learned router and resolver adapters (phase 10a) that load JSON artifacts through the filesystem `ModelRegistry` with a digest check; they never import an ML library or unpickle anything, and the feature code they use is shared with `bank-ml` training (`ml/README.md`). A lingua-language-detector adapter waits for the team's approval of its size. An OpenTelemetry adapter arrives in phase 15. `docs/architecture/ports-and-adapters.md` has the full table.

## Who may import it

`api` and `bootstrap` only; in practice only `bootstrap/container.py` constructs adapters. Adapters may import `application`, `policy`, `ports`, and `domain`.

## How to extend

1. Implement the port's Protocol in `adapters/<area>/<technology>/`.
2. Add a backend to `READ_BACKENDS` or `WRITE_BACKENDS` in `services/api/tests/bank_agent_contracts.py` (marked `integration` when it needs a database), so the port's shared contract suite in `services/api/tests/contracts/` runs against it.
3. Select it by name in `bootstrap/container.py` (persistence in `bootstrap/persistence.py`), driven by settings.

### Adding a persistence backend

A new backend (for example another SQL database) must provide all of the following before the composition root may select it:

1. A unit of work factory whose units of work implement every repository property of `ports/unit_of_work.py`, including `audit`, `credit_profiles`, `credit_applications`, and `action_ledger`, and a `SessionStore` and standalone `AuditLog`.
2. Customer scoping inside every query, from the bound `AccessContext` only; no method takes a customer identifier. Another customer's record behaves exactly like a missing one.
3. The same idempotency (natural keys per customer), append-only (identical replay is a no-op, a different document fails), and optimistic concurrency rules as the memory adapter; a write must never wait indefinitely on another open unit of work.
4. Defense in depth where the technology allows it: a database role that owns nothing, cannot bypass row-level security, and has only the privileges the service needs.
5. Mapper modules for every aggregate, with round-trip unit tests (see `tests/unit/adapters/persistence/test_postgres_mappers.py`).
6. A contract-suite backend class like `services/api/tests/bank_agent_postgres_backend.py`, registered in both backend lists, plus isolation tests like `tests/integration/test_row_level_security.py`.
7. Seeding through the same domain objects the repositories return (`adapters/persistence/postgres/seed.py` is the pattern).

A language model concern (caching, a new provider) is a new `LlmDecorator` subclass or a new `ChatCompletion`, wired in `bootstrap/llm.py`; `docs/architecture/llm-gateway.md` explains the stack.
4. Customer data access sets the PostgreSQL row-level security context inside each transaction and connects as the application role, which owns no tables and has no `BYPASSRLS`.

## How to test

Integration tests against real PostgreSQL through testcontainers (`services/api/tests/integration/`), and the shared contract suites. Coverage gate: 80% line coverage.
