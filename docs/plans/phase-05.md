# Phase 05 plan: mock core banking, identity, and customer isolation

Status: the prompt asks for plan mode. The human delegated plan approval to the orchestrator, which pre-approved a plan that follows the prompt, CLAUDE.md, and the phase 02 and 02b contracts. Every open question below is decided by the session under the orchestrator's pre-approval. Written against commit `26fded9`, after phase 04.

## What already exists

| Piece | State before this phase |
|---|---|
| Ports | Every repository port, `UnitOfWork`, `SessionStore`, `AuditLog`, `IdentityProvider`, `OtpSender`, `CreditProductCatalog`, `Clock`, `IdGenerator` (phases 02 and 02b) |
| Domain | `AccessContext` (the "session context"), `Session` with expiry math, `OtpChallenge`, `VerifiedIdentity`, `BalanceView`, `PaymentStatusView`, `StatementSummary`, `CardStatusView`, `CreditApplicationIntake`, `Verification`, `ToolName`, `ToolFailureMode`, typed errors |
| Adapters | Memory repositories and session store; DuckDB gold readers (phase 03) with row mappers; a PostgreSQL readiness check |
| Database | `deploy/postgres/init/10-roles.sh`: owner `bank_owner`, application role `bank_app` (`NOBYPASSRLS`, owns nothing), schema `app`, default privileges |
| Contract suites | `READ_BACKENDS` (memory, duckdb) and `WRITE_BACKENDS` (memory); phase 05 adds `postgres` to both |

## Schema (Alembic, schema `app`)

Migrations live in `services/api/src/bank_agent/adapters/persistence/postgres/migrations/` so the seed, the tests, and a `bank-agent db upgrade` command can run them programmatically as the owner role.

| Table | Key columns | Constraints and indexes |
|---|---|---|
| `customers` | `customer_id` PK, `country`, `segment`, `status`, `first_name`, `snapshot_date` | Checks on every enum; read only for the application role |
| `identity_directory` | `customer_id` PK FK, `persona_id` unique, `document_lookup` unique (HMAC), `phone_last4_lookup` (HMAC) | Never holds a raw document number or phone; read only |
| `staff_members` | `staff_id` PK, `role` (agent or evaluator), `persona_id` unique, `display_name` | Agent and evaluator personas |
| `products` | `product_id` PK, `customer_id` FK, type, status, last 4, currency, `current_balance`, `credit_limit`, `annual_interest_rate`, `opened_on`, `expires_on`, `balance_as_of`, `days_past_due` | Unique `(product_id, customer_id)` for composite foreign keys; a balance needs `balance_as_of`; limit and days past due non-negative; index `(customer_id, product_id)`. The application role may update only the `status` column (column privilege) |
| `transactions` | `transaction_id` PK, `customer_id`, `product_id`, `occurred_at`, type, category, amount, currency, `amount_usd`, channel, status, merchant fields, location, fraud label and score | Composite FK `(product_id, customer_id)` to `products`, so a transaction can never sit on another customer's product; indexes `(customer_id, occurred_at desc, transaction_id)`, `(customer_id, product_id, occurred_at desc)`, `(customer_id, transaction_type, occurred_at desc)`; read only |
| `historical_complaints` | intake-time fields only | index `(customer_id, created_at desc)`; read only |
| `credit_profiles` | `customer_id` PK FK, score, income and currency, tenure, product count, max days past due, total limit and currency, utilization, `as_of` | Read only; no agent or evaluator policy |
| `dispute_cases` | `case_id` PK, `customer_id`, `transaction_id`, `product_id`, reason, status, amount, currency, instants, `idempotency_key`, `version`, `document` JSONB | Unique `(customer_id, idempotency_key)`; composite FK `(transaction_id, customer_id)` to `transactions`; checks that `document` agrees with the scalar columns; indexes for list, open-for-transaction |
| `credit_applications` | `application_id` PK, `customer_id`, `product_code`, status, amount, currency, term, `idempotency_key`, instants, `version`, `document` JSONB | Unique `(customer_id, idempotency_key)`; status check allows only `submitted`, `under_human_review`, `withdrawn`, `closed` |
| `sessions` | `session_id` PK, `token_digest` unique (SHA-256 of the 256-bit token), `lineage_id`, role, customer or staff FK, `auth_level`, `created_at`, `last_seen_at`, `idle_timeout_seconds`, `absolute_expires_at`, `step_up_expires_at`, `revoked_at` | Subject check (a customer session names only a customer); `auth_level` never `step_up` |
| `trust_events` | `lineage_id`, `sequence`, `occurred_at`, `document` | Append-only like the audit tables (the `SessionStore` port needs it) |
| `otp_challenges` | `challenge_id` PK, `purpose` (login or step_up), `subject_key` (HMAC of the identification), customer or staff FK (null for an unknown person), `session_id` for step-up, `code_hash`, `salt`, `attempts`, `max_attempts`, `expires_at`, `consumed_at`, `locked_until` | index `(subject_key, created_at desc)` for the lockout check |
| `conversations`, `turns` | ids, `customer_id`, lineage, status, version, sequence, `document` JSONB | Unique `(conversation_id, sequence)`; turns carry `customer_id` for RLS |
| `execution_records` | `turn_id` PK, `conversation_id`, `customer_id`, `recorded_at`, `content_digest`, `document` | Append-only |
| `handoffs` | `handoff_id` PK, `customer_id`, `case_ref`, `application_ref`, status, priority, reason, language, `sla_due`, `content_digest`, `document` (immutable), lifecycle columns | A trigger refuses any change of `document`; indexes for the inbox query |
| `audit_events` | `event_id` PK, `occurred_at`, actor, action, target, outcome, `content_digest`, `document` | Append-only |
| `eval.evaluation_runs` | run id, instants, scenario set version, git sha, status, summary | In schema `eval`, reachable only by the NOLOGIN role `bank_evaluator` (phase 14 writes it) |

Idempotent inserts use `ON CONFLICT DO NOTHING` on the natural key; append-only inserts use an arbiter unique index on `(id, content_digest)`, so an identical replay is a no-op and a different document with the same id raises a unique violation (mapped to `AppendOnlyViolationError`) without needing a SELECT policy.

### Append-only enforcement

`execution_records`, `audit_events`, and `trust_events`: `REVOKE UPDATE, DELETE, TRUNCATE` from the application role, and a `BEFORE UPDATE OR DELETE` trigger that raises for everyone, including the owner.

### Row-level security

- `ENABLE` and `FORCE ROW LEVEL SECURITY` on every table with customer data (all tables above except `staff_members`, which holds no customer data, but it gets RLS too for the identity role only).
- Customer policies: `customer_id = current_setting('app.customer_id', true) AND current_setting('app.role', true) = 'customer'`.
- Agent policies (`app.role = 'agent'`): every handoff (select, lifecycle update); a dispute case or credit application only when a handoff references it. No agent policy on `customers`, `products`, `transactions`, `historical_complaints`, `credit_profiles`, `conversations`, `turns`, or `execution_records`.
- Evaluator policies (`app.role = 'evaluator'`): read `execution_records`, `audit_events`, and `handoffs`.
- Identity policies (`app.role = 'identity'`): `identity_directory`, `staff_members`, `otp_challenges`, `sessions`, `trust_events`, and insert on `audit_events` (login events). The identity service and the session store set this role; no customer data table has an identity policy.
- Seed policies: `TO` the migrating owner role only and only when `app.role = 'seed'`, so the owner must opt in explicitly and the application role can never use them.
- Unset context: `current_setting(..., true)` returns null or empty, so every policy is false and queries return zero rows.
- The database cannot verify who set `app.customer_id`: the application role sets its own context. RLS is therefore defense in depth behind tool-layer scoping, not the primary control (ADR 0009).

## Repositories (PostgreSQL adapters)

- `PostgresDatabase` owns one SQLAlchemy async engine (asyncpg). `PostgresUnitOfWorkFactory(database)(context)` opens a connection and a transaction, runs `select set_config('app.customer_id', :c, true), set_config('app.role', :r, true), set_config('lock_timeout', ...)` with bound parameters, and exposes the repositories. Repositories take the unit of work's connection and its `AccessContext`; there is no constructor that takes a connection without a context.
- Concurrency: writes lock rows with `FOR UPDATE NOWAIT` inside a savepoint. When another open unit of work holds the row, the unit of work is marked conflicted, and `commit` raises `ConcurrencyConflictError` and applies nothing (the memory adapter's optimistic behavior, without blocking a request on a lock). A stale version or status raises immediately.
- Mappers: `adapters/persistence/postgres/mappers/` (one module per aggregate): row to domain and domain to row, with canonical JSON and the content digest.
- Tables are declared once with SQLAlchemy Core (`tables.py`); the migration is written by hand and a test compares it with the declared metadata.

## Seed

- `bank-data seed --customers N [--source]` (the data platform gains a workspace dependency on `bank-agent`, like `bank-evals`): runs the migrations as the owner, selects personas from `data_platform/seed/personas.yaml` by named criteria evaluated in DuckDB over the gold serving files, fills up to N customers by a seeded hash, maps rows with the phase 03 row mappers, and upserts everything through `PostgresSeeder` with `app.role = 'seed'`. Re-running changes nothing (upserts on primary keys; the seed never touches written tables such as sessions, cases created by the workflow, or audit events).
- Seeded fixtures for the evaluation needs that the data cannot supply: an open dispute case, an existing credit application, a pending payment and a reversed payment when the chosen customer lacks one are never invented; criteria select customers that already have them. Only the open dispute case and the existing application are created by the seed (the data has no dispute cases or applications), each labeled `seed` in its idempotency key.
- `make seed` runs it against the compose PostgreSQL (`SEED_CUSTOMERS`, default 200) and appears in `make help`.
- Personas cover the prompt's list; `docs/demo/personas.md` records criteria and play instructions, never personal data.

## Identity (`adapters/identity`)

- `MockIdentityProvider` implements `IdentityProvider` over a `ChallengeStore` (memory for unit tests, PostgreSQL for integration) and a `DirectoryLookup`.
- Codes: six digits from `secrets.randbelow`, `code_hash = HMAC-SHA256(k_otp, salt || challenge_id || code)` with a 16-byte random salt per challenge and `k_otp` derived from `SESSION_SECRET` by HMAC with a fixed label; `hmac.compare_digest`; 5-minute expiry; 5 attempts; then the subject key is locked for a 15-minute cooldown. Unknown persons get a real-looking challenge that always fails with the same `IdentityChallengeFailedError`, and count toward the same lockout.
- `DemoOtpSender`: code in the receipt only with `DEMO_MODE=true`; otherwise a delivery event without the code.
- `SessionService` (application layer): verify, create a session (256-bit token from `secrets`, stored as its SHA-256 digest, returned once), idle 15 minutes, absolute 60 minutes, `otp_verified`; step-up opens a 5-minute window and rotates the session (privilege change); logout revokes; `resolve(token)` touches or reports expiry. Lifetimes are constants in `SessionPolicy`, not environment variables.

## Banking tools (`application/tools`)

- `SessionContext`: the validated session plus its `AccessContext` and the step-up state at the call instant. `BankingTools.for_session(context)` returns `SessionTools`, whose methods take only tool arguments.
- Read tools as listed in the prompt; ids of another customer behave as not found (`None` or the entity's `NotFoundError`). `get_statement_summary` caps the period at `DEFAULT_MAX_STATEMENT_DAYS = 92` until phase 06 supplies the policy parameter, and refuses a mixed-currency result by construction (totals per currency). `get_my_credit_profile` lives on a separate `EngineOnlyTools` object, never on `SessionTools`, so no allowlist can reach it.
- Write tools: `create_dispute_case`, `block_card` (requires a valid step-up window; idempotent through an audit-backed idempotency record: a repeated key returns the first outcome), `submit_credit_application`. No unblock or replacement tool.
- Verification helpers read back each write in a fresh unit of work and return a `Verification` with an evidence reference.
- `ToolFailureInjector` wraps `SessionTools` (same Protocol) with timeout, transient, permanent, and partial-write modes; the composition root refuses it in production.
- Every tool call appends an audit event (actor, action, target, outcome, redacted arguments) in the same unit of work as the write; read tools audit too.

## Files to create or change

| Path | Change |
|---|---|
| `services/api/pyproject.toml`, `uv.lock` | `alembic` (named in the CLAUDE.md stack) |
| `services/api/src/bank_agent/adapters/persistence/postgres/` | `database.py`, `tables.py`, `migrations/` (env and `0001_core_banking.py`), `unit_of_work.py`, `repositories/`, `mappers/`, `sessions.py`, `audit.py`, `seed.py`, `challenges.py`, `directory.py` |
| `services/api/src/bank_agent/adapters/identity/` | `provider.py`, `codes.py`, `sender.py`, `memory.py` |
| `services/api/src/bank_agent/application/identity/` | `session_service.py`, `policy.py` |
| `services/api/src/bank_agent/application/tools/` | `context.py`, `banking.py`, `verification.py`, `failure_injection.py`, `audit.py`, `protocols.py` |
| `services/api/src/bank_agent/bootstrap/` | `persistence.py` (engine, factory, session store, identity), container wiring, the injector guard |
| `services/api/src/bank_agent/cli.py` | `bank-agent db upgrade` |
| `data_platform/src/bank_data/seed/`, `data_platform/seed/personas.yaml`, `bank_data/cli.py`, `data_platform/pyproject.toml` | Persona selection and the `seed` command |
| `Makefile` | `seed` (and `db-upgrade`) |
| `services/api/tests/bank_agent_postgres.py`, `tests/contracts/*` | `PostgresBackend` in `READ_BACKENDS` and `WRITE_BACKENDS` |
| Docs | `docs/security/identity-and-sessions.md`, `docs/security/data-isolation.md`, `docs/demo/personas.md`, `services/api/src/bank_agent/adapters/README.md`, ADRs 0008, 0009, 0010, ADR index, `docs/PROGRESS.md`, `docs/BACKLOG.md` |

## Tests to add

- Integration (testcontainers): RLS isolation through every repository and raw SQL without context; agent limits; evaluator limits and the `eval` schema isolation; append-only UPDATE and DELETE fail (application role and owner); OTP lifecycle (success, wrong code, expiry, lockout after 5, cooldown); session idle and absolute expiry, rotation, revocation; step-up required for `block_card`; idempotent writes; credit RLS and the status check constraint; every read tool scoped by session; statements never mix currencies and balances carry `as_of`; verification detecting an injected partial write; seed idempotency; the migration matches `tables.py`.
- Unit: code hashing and constant-time comparison, session expiry math with `FixedClock`, generic error messages, mapper round trips, the injector, the provider over the memory challenge store, tool logic over memory adapters.
- Contract: the PostgreSQL adapters in every shared suite, including the phase 02b credit suites.

## Risks

- The contract suites assume memory semantics for concurrent units of work; row locks would block. Mitigated by `NOWAIT` plus the conflicted flag.
- Testcontainers startup time: one container per test session, a fresh database per test through `TRUNCATE` as the owner (triggers on append-only tables are bypassed with `session_replication_role = replica` in test cleanup only).
- The seed depends on the gold files; CI has only the committed sample. Seed integration tests use the sample warehouse built from a small fixture gold directory.
- Scope is large; work lands in vertical increments (schema, repositories, identity, tools, seed, docs).

## Open questions, each decided by the session under the orchestrator's pre-approval

1. **Session context type.** Reuse `AccessContext` as the database context (it already documents itself as the phase 05 session context) and add `SessionContext` in the application layer for tools (session plus access context). Decided by the session under the orchestrator's pre-approval.
2. **Server secret for code hashes and identity lookups.** Derive purpose-specific keys from `SESSION_SECRET` with HMAC and fixed labels instead of adding new variables; production already refuses a weak `SESSION_SECRET`. Decided by the session under the orchestrator's pre-approval.
3. **Where the seed lives.** `bank-data seed` in the data platform (as the prompt says), depending on `bank-agent` for the schema, mappers, and seeder. Decided by the session under the orchestrator's pre-approval.
4. **Document storage.** Aggregates with nested structure (cases, applications, conversations, turns, records, handoffs, audit events) store the validated domain document as JSONB plus the scalar columns used by queries, constraints, and RLS, with check constraints tying them together. Decided by the session under the orchestrator's pre-approval.
5. **Evaluator isolation.** A separate `eval` schema and NOLOGIN role `bank_evaluator` with no privileges on customer data tables, plus `app.role = 'evaluator'` policies limited to records, audit events, and handoffs. Decided by the session under the orchestrator's pre-approval.
6. **Statement period default.** 92 days until phase 06 sets the policy parameter. Decided by the session under the orchestrator's pre-approval.
7. **`block_card` idempotency.** The product row has no idempotency column; a repeated key is recognized from the tool's own audit record of the first successful call (unique per customer and key in an `action_idempotency` table), and a block of an already blocked card with a new key succeeds as a no-op. Decided by the session under the orchestrator's pre-approval.
8. **Lifetimes.** Fixed constants in code (`SessionPolicy`) matching CLAUDE.md section 7, not environment variables. Decided by the session under the orchestrator's pre-approval.
9. **Seeded write fixtures.** Only the open dispute case and the existing credit application are synthesized by the seed; everything else comes from gold rows chosen by criteria. Decided by the session under the orchestrator's pre-approval.
