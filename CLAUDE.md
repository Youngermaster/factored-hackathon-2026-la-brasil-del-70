# CLAUDE.md

This file is the working agreement for every Claude Code session in this repository. Read it completely at the start of every session. When a phase prompt conflicts with this file, this file wins, unless the prompt explicitly names the rule it overrides.

## 1. Mission

We are building an AI-first banking customer-service system for the Factored AI & Data Hackathon 2026. The organizer requirements are summarized in `docs/organizer/BRIEF.md` and the dataset schema in `docs/organizer/DATA_DICTIONARY.md`. Read both before designing anything.

**Scope (human decision, 2026-09-26): four workflows, each built in depth.**

| Workflow id | Covers | What the system may do |
|---|---|---|
| `account_inquiry` | Account and payment inquiries: balances, payment status, statement summaries | Read only, always stating the as-of date of the data |
| `card_support` | Card status, protective card block, unblock and replacement requests | Block a card (confirmation, step-up, verified read-back). Unblock and replacement requests go to a human |
| `dispute` | Transaction-dispute intake and dispute status | Open a dispute case (confirmation, verified read-back), with an optional protective card block |
| `credit` | Credit-product information and eligibility support | Answer from the synthetic product catalog, give an indicative eligibility result from the synthetic eligibility service, and record an application intake for human review. Never a lending decision |

Requests outside these four workflows, and unsupported requests inside them, get a clarifying question, a clause-backed abstention, or a handoff. Every workflow has a normal path, an ambiguous or unsupported path, and a human-escalation path, each demonstrated in Spanish and Portuguese.

**Why this deviates from the brief.** The brief says depth over breadth and that more workflows earn no bonus. The team chose breadth anyway (see `docs/plans/kickoff-notes.md`). The scoring risk is real: the extra workflows earn nothing by themselves, and four shallow flows would score worse than one deep one. We manage that risk as follows:

- Every workflow meets the same depth bar: policy clauses, bound clauses per state, an explicit state machine, verified actions, a structured handoff, es and pt coverage, and a page in `docs/workflows/`.
- Every workflow is evaluated separately, with its own scenario slice, metrics, and failure table. Aggregate numbers are never reported without the per-workflow numbers next to them.
- The shared engine, policy kernel, grounding verifier, and evaluation harness carry the engineering depth once, for all four.
- If a workflow cannot meet the bar before the deadline, it is cut back to clarify, abstain, or hand off, and the cut is documented as a limitation. It is never shipped shallow.

**Credit rules (from the brief, mandatory for the `credit` workflow).**

- Conversation handling, predictive risk estimates, and eligibility policy are separate components behind separate ports (`RiskEstimator` and `EligibilityPolicy`).
- Eligibility comes only from the synthetic eligibility service, which is clearly labeled synthetic. The language model never invents eligibility rules, never states or implies approval, and never receives the risk estimate or the customer's credit profile.
- Every eligibility answer shows its reasons, its uncertainty, and a review path. Missing data and borderline cases go to human review.
- No live lending decisions and no movement of money, in any workflow.

Design thesis: the language model understands, deterministic code decides, and evidence proves it.

Facts from the brief that drive every decision:

- Depth over breadth. Implementing more workflows earns nothing. The scope decision above explains how the team handles this.
- Required behaviors: a normal resolution path, an ambiguous or unsupported request, and a case requiring human intervention, in Spanish and Portuguese.
- Permissions and policy are enforced outside model-generated prose. The system reports only actions whose outcomes it has verified.
- Identity comes from a trusted test session. A national ID or customer number alone never proves identity. Customer isolation is enforced in the service or tool layer.
- Handoffs carry the request, verified facts, actions taken, supporting evidence, and unresolved questions. They never dump raw transcripts.
- Explanations come from sources, policy rules, and execution records. Hidden model chain-of-thought is never stored, shown, or offered as an audit artifact.
- Evaluation compares baselines and the proposed system on the same held-out workload, using the brief's outcome definitions: safe automated resolution, containment, escalation quality, unsafe outcomes, operating efficiency.
- Offline measurements, simulations, and projected savings are always labeled separately.

## 2. Non-negotiable rules

1. No emojis anywhere: code, comments, docs, commit messages, UI copy, logs, test names, fixtures, and generated reports. Use words or icon components. `make check` enforces this.
2. No AI attribution.
   - Never add `Co-Authored-By` trailers for Claude or any AI tool.
   - Never add "Generated with Claude Code" or similar lines to commits, pull requests, docs, or code comments.
   - Commits are authored by the human running the session. Never change `git config user.*`.
   - A commit-msg hook and a CI check enforce this. Never bypass them.
3. Git safety.
   - Never run `git commit --no-verify`.
   - Never force-push, and never rewrite published history.
   - Never push unless the human explicitly asks.
4. No secrets in the repository, in logs, or in model prompts.
   - Credentials come only from environment variables loaded by pydantic-settings.
   - Never read, print, or commit `.env`. Scripts must never echo secret values.
   - The organizer data dictionary PDF contains credentials, so it must never be committed or pasted anywhere.
5. Organizer data in git is limited to one bounded, documented sample. Full data lives under `data/`, which is gitignored. The only organizer data that may be committed is the extract in `data_platform/sample/`, and only under these conditions:
   - `make data-sample` produces it from the pipeline, deterministically (customers chosen by a seeded hash and followed through every table). It is never hand-picked or hand-edited, and ad hoc extracts are never committed.
   - It holds at most 5,000 rows in total across all tables, and never a full table.
   - Direct identifiers (document numbers, names, emails, phones, addresses, birth dates) are replaced with deterministic, format-valid pseudonyms, so the data contracts still pass and no identifier is copied verbatim.
   - `data_platform/sample/README.md` states the source, the dataset version (snapshot dates and manifest etags), the extraction command, query, and seed, the row count per table, the column treatments, and that it is organizer-provided synthetic data subject to the organizer's data-use terms.
   - It never contains credentials, `.env` values, or anything taken from the data dictionary PDF.
   - A check in `make check` fails when the sample exceeds the row limit or the README is missing.
   - The organizer's data-use terms are checked before the repository is made public (phase 17 re-verifies). If they forbid redistribution or are unclear, stop and ask the human. Never rewrite history to remove the sample without the human's explicit instruction.

   Test fixtures stay small, synthetic, team-made, and labeled as fixtures.
6. Minimize data sent to external model providers. Send only the fields a prompt needs. Never send document numbers, full names, emails, phone numbers, or addresses.
7. No placeholder implementations for required behavior: no `TODO: implement`, no `pass` bodies, no hard-coded fake returns in production code paths. If something is out of scope for the current phase, record it in `docs/BACKLOG.md` with the reason and the phase that owns it.
8. Never disable, skip, xfail, or weaken tests, linters, type checks, coverage gates, or security checks to make a phase pass. Fix the cause.
9. Language rules.
   - Code, identifiers, comments, and documentation are in English.
   - Customer-facing copy exists in Spanish and Portuguese.
   - The agent and evaluator console has English and Spanish.
10. Dependencies. Before adding a runtime dependency, check that it is maintained and appropriately licensed. Pin it through the lockfile, and note the reason in the phase log. Ask the human before adding anything large (over roughly 50 MB installed) or security-sensitive.

## 3. Stack

Backend and data (Python 3.12, uv workspace):

- API and models: FastAPI, Pydantic v2, pydantic-settings.
- Persistence: SQLAlchemy 2 (async) with Alembic, and PostgreSQL 16 with row-level security.
- Data platform: DuckDB plus dbt-duckdb, with Pandera for ingestion contracts.
- Observability: structlog and OpenTelemetry.
- ML: MLflow (tracking and local registry), scikit-learn, and LightGBM. sentence-transformers lives in an optional `ml` extra that is never installed in the API runtime image.
- Tests: pytest, pytest-asyncio, Hypothesis, testcontainers, pytest-socket, and coverage.
- Quality: ruff (lint and format), mypy (strict for domain, ports, policy, and application), import-linter, bandit, and pip-audit.
- CLIs: typer.

Frontend (`apps/web`):

- Core: Vite, React 19, and TypeScript in strict mode, with React Router.
- State and data: TanStack Query for server state. Zustand only under the rule in section 6.
- UI: Radix UI primitives, Tailwind CSS v4 with design tokens as CSS variables, and one outline icon set.
- Forms and i18n: react-hook-form with zod, and i18next.
- API types: openapi-typescript plus openapi-fetch.
- Tests: Vitest, React Testing Library, MSW, and vitest-axe.
- Quality: ESLint flat config with import boundary rules, and Prettier.
- Package manager: pnpm, pinned through the `packageManager` field, with a committed `pnpm-lock.yaml`. Later phase prompts that say npm or npx mean pnpm or `pnpm dlx` (for example `npm ci` is `pnpm install --frozen-lockfile`, `npm run X` is `pnpm run X`, and `npm audit --omit=dev` is `pnpm audit --prod`).

Operations:

- Docker (multi-stage, non-root) and docker compose.
- GitHub Actions and pre-commit with gitleaks.
- Caddy for TLS in deployment.

## 4. Repository layout

```text
.
├── CLAUDE.md
├── README.md
├── Makefile
├── pyproject.toml                  uv workspace root, shared tool config
├── docker-compose.yml              development stack
├── apps/
│   └── web/                        Vite + React + TypeScript
│       └── src/
│           ├── app/                providers, router, composition root
│           ├── shared/             ui primitives, api client, i18n, lib
│           ├── entities/           domain types and presentational pieces
│           ├── features/           self-contained features (api, model, ui, index.ts)
│           └── pages/              route-level composition only
├── services/
│   └── api/                        Python package bank_agent
│       ├── src/bank_agent/
│       │   ├── domain/             entities, value objects, errors (pure)
│       │   ├── ports/              Protocol interfaces
│       │   ├── policy/             policy pack loader, rules, evaluator (pure)
│       │   ├── application/        workflow engine, workflows, use cases
│       │   ├── adapters/           persistence, llm, retrieval, identity, models, telemetry
│       │   ├── api/                FastAPI app, routers, DTOs, security, middleware
│       │   ├── bootstrap/          settings, composition root
│       │   └── prompts/            versioned prompt files
│       └── tests/{unit,integration,contracts}
├── data_platform/                  ingestion, contracts, dbt project, reports, committed sample (rule 5)
├── ml/                             bank_ml: router and resolver pipelines
├── evals/                          bank_evals: scenarios, harness, graders, reports
├── policies/                       synthetic policy pack (es, pt), bindings, matrix
├── contracts/                      JSON Schemas, OpenAPI snapshot
├── deploy/                         production compose, Caddyfile, scripts
├── docs/                           architecture, workflows, ADRs, data, models, evaluation
├── scripts/                        hooks and repository checks
└── data/                           gitignored: raw, warehouse, artifacts
```

## 5. Backend architecture rules

**Dependency direction.** The architecture is hexagonal, and imports flow inward only: `domain` <- `ports` <- `policy` <- `application` <- `adapters` <- `api` and `bootstrap`. import-linter contracts in `pyproject.toml` enforce this, and `make check` fails on violations.

**The domain layer is pure.** It contains Pydantic models or dataclasses, value objects (for example `Money` with an explicit currency and `Decimal` amounts, never floats), enums, and typed domain errors. It has no I/O and no framework imports.

**Repository pattern.**
- Every aggregate has a repository Protocol in `ports/`.
- Implementations live in `adapters/persistence/{postgres,duckdb,memory}` and are selected by settings.
- Repositories return domain objects, never ORM rows or dataframes.
- Every implementation passes the shared contract suite for its port in `tests/contracts/`: one parameterized test class, run against every adapter.

**Composition over modification.** Cross-cutting behavior is added by wrapping a port with a decorator that implements the same Protocol:
- bounded retry, timeout, circuit breaker,
- budget guard, tracing, caching,
- redaction, failure injection (tests and evals only).

Decorators are stacked in the composition root like building blocks. Never put cross-cutting logic inside business code.

**Composition root.** `bootstrap/container.py` is the only module that knows concrete adapters. FastAPI dependencies, CLIs, and the evaluation harness all resolve from it.

**Policy.**
- Rules are pure functions registered by rule id in `policy/rules/`.
- Rule parameters and customer-facing clause text live in files under `policies/`, not in code.
- The evaluator returns a `Decision` that names every rule id and clause version it used.
- Adding a rule means a new function, a clause file, and tests. Workflow code only changes when a new state is needed.
- Credit eligibility rules are policy rules like any other (`ELG.*`). The synthetic eligibility service implements the `EligibilityPolicy` port on top of the evaluator, and its parameters live in `policies/`, labeled synthetic.

**Replaceable models.**
- The intent router, transaction resolver, credit risk estimator, retriever, and LLM client are ports.
- Implementations are selected by name and version, or by an alias such as `champion`, through settings.
- Artifacts load through a `ModelRegistry` port (filesystem adapter by default, MLflow adapter optional).
- Swapping a model never requires workflow changes.

**Prompts.**
- Versioned files live at `bank_agent/prompts/<prompt_id>/<version>.md`, with front matter (id, version, purpose, inputs, output model, changelog).
- Code references prompts by id and version.
- Execution records store the version used.

**Customer isolation.**
- Tools the model can influence never accept customer identifiers. The session context injects them.
- Customer data access goes through repositories that set the PostgreSQL row-level security context inside each transaction.
- The application database role does not own the tables and has no BYPASSRLS.

**Errors.** Typed domain errors are mapped to RFC 9457 problem details in one place, and internal details never leak to clients.

**Determinism.** Time comes from a `Clock` port and identifiers from an `IdGenerator` port, so tests can freeze both.

**Configuration.** pydantic-settings classes are organized per concern. Only `bootstrap/` reads the environment. Production settings refuse to start with default or empty secrets.

## 6. Frontend architecture rules

**Layers.** Imports flow downward only: `pages` -> `features` -> `entities` -> `shared`.
- A feature exposes its public API through `features/<name>/index.ts`.
- Other code never imports a feature's internals.
- ESLint boundary rules enforce this.

**Composition over configuration.**
- Build compound components (for example `Conversation.Root`, `Conversation.Messages`, `Conversation.Composer`) that share state through a scoped context.
- Prefer `children` and slots over growing lists of boolean props.

**No prop drilling beyond two levels.** Use a feature-scoped context or a query hook instead.

**State.**
- Server state lives only in TanStack Query.
- Local UI state stays in components.
- Feature-scoped shared state uses context with `useReducer`.
- Zustand is allowed only when state must be shared across features or routes and changes frequently. Each store needs a written justification in `docs/frontend/state.md`.

**API access.**
- Types are generated from the backend OpenAPI into `shared/api/generated/`.
- The typed client uses `credentials: 'include'`, sends the CSRF header, and parses problem details.
- No `any` types.

**Security.**
- Never store tokens in localStorage or sessionStorage; the session is an httpOnly cookie.
- Never use `dangerouslySetInnerHTML`.
- Render model output as plain text.
- No inline scripts, so the build works under a strict CSP.
- External links get `rel="noopener noreferrer"`.

**UI quality.**
- Follow the installed taste skills (`design-taste-frontend`, `minimalist-ui`) and record design decisions in `docs/design/DESIGN.md`.
- Meet WCAG 2.2 AA: keyboard access, visible focus, sufficient contrast, and `aria-live` for chat updates.
- No emojis. Use one icon library. No em dashes in UI copy.

**i18n.**
- Every user-facing string lives in locale files (`es`, `pt`, `en`).
- Money, dates, and numbers are formatted with `Intl` per locale (`es-MX`, `es-CO`, `es-AR`, `pt-BR`).

## 7. Security standards

These follow OWASP ASVS level 2 practices and apply to every phase.

**Authentication and sessions.**
- One-time codes are hashed at rest, expire in 5 minutes, allow at most 5 attempts before lockout, and are compared in constant time.
- Sessions are server-side, with opaque random ids stored hashed, an idle expiry, an absolute expiry, and rotation on privilege change.
- Write actions require step-up authentication.

**Cookies and CSRF.**
- Cookies are `HttpOnly`, `Secure`, `SameSite=Strict`, with the `__Host-` prefix in production.
- CSRF protection uses a double-submit token on every state-changing request.

**Authorization.**
- Role-based access control covers customer, agent, and evaluator roles.
- Row-level security acts as defense in depth.
- Cross-customer resource access returns 404, not 403, so resources cannot be enumerated.

**Input and output.**
- Every request body is validated by Pydantic, with explicit maximum lengths.
- Oversized payloads are rejected.
- Output is encoded for its context.

**HTTP.**
- CORS uses an allowlist.
- Security headers are always set: CSP, HSTS in production, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, and `frame-ancestors 'none'`.
- Rate limits apply per IP and per session, stricter on authentication endpoints.

**Prompt injection.**
- Records, retrieved text, and user input are treated as data, wrapped in delimiters, and never allowed to select tools.
- Tools come from a per-state allowlist, and every tool argument is validated.
- Model output is never executed.

**Secrets.**
- Environment only. gitleaks runs in pre-commit and in CI across the full history.

**Supply chain.**
- Lockfiles are committed.
- pip-audit and `pnpm audit --prod --audit-level high` run in CI and fail on high-severity findings.
- bandit runs in CI.

**Containers.**
- Non-root user, read-only root filesystem where possible, dropped capabilities, pinned base images, and health checks.

**Logging.**
- Logs are structured JSON with a redaction processor that masks identifiers, contact details, tokens, and secrets.
- Retention is configured and documented.

**Audit.**
- Execution records and audit events are append-only at the database level.

## 8. Testing rules

**Unit tests** (`tests/unit`):
- No network, database, or filesystem access outside temporary directories. pytest-socket disables the network.
- Use in-memory adapters, `FakeLLM`, `FixedClock`, and deterministic id generators.

**Integration tests** (`tests/integration`):
- Use real PostgreSQL (testcontainers or the compose service) and real DuckDB files.
- Drive the FastAPI app through the httpx ASGI transport.
- Use `FakeLLM` or recorded cassettes. Tests never call a live model.

**Contract tests** (`tests/contracts`): every adapter runs the shared suite for its port.

**Property tests** (Hypothesis): policy kernel invariants, trust-state monotonicity, and money arithmetic.

**Frontend tests:**
- Vitest and React Testing Library for primitives, hooks, and formatters.
- Integration tests per feature using MSW handlers typed from the generated API types.
- vitest-axe checks on key screens.

**Coverage gates** (enforced in CI):
- 90% line coverage for `domain`, `ports`, `policy`, and `application`.
- 80% for `adapters` and `api`.
- 70% for web features.

**Naming and regressions.** Test names describe behavior, for example `test_rejects_dispute_after_window_closes`. Every bug fix adds a regression test.

**Scope.** Browser end-to-end tests are out of scope. The evaluation harness (`make eval`) is separate from the test suite.

## 9. Documentation rules

**Format.**
- Markdown with Mermaid only. Diagrams are code in fenced `mermaid` blocks.
- `make docs-check` validates Markdown style and Mermaid syntax.

**Package READMEs.** Every package and app has a `README.md` covering:
- its responsibility,
- its public interfaces,
- how to extend it (add an adapter, model, rule, prompt, or feature),
- how to test it.

**ADRs.** Record each choice between real alternatives in `docs/adr/NNNN-title.md`, using the MADR format with context, options, decision, and consequences. Keep `docs/adr/README.md` as the index.

**Workflow docs.** Each workflow gets a page in `docs/workflows/` containing:
- a `stateDiagram-v2`,
- sequence diagrams for the normal, ambiguous, and escalation paths,
- tables mapping state to rules, clauses, and tools.

**Keeping docs current.** Docs change in the same commit as the code they describe. Generated reports carry the generation timestamp, the git sha, and the input versions.

**Tone.** Plain and precise. No emojis and no marketing language. State limitations explicitly.

## 10. Commands

Make targets are added by the phase that implements them, and `make help` lists what exists. The expected set:

| Command | Purpose |
|---|---|
| `make setup` | Install Python and web dependencies and pre-commit hooks |
| `make up` / `make down` | Start or stop the development stack |
| `make check` | Lint, format check, typecheck, import boundaries, unit and integration tests, emoji check, attribution check, gitleaks |
| `make test-unit`, `make test-integration`, `make test-web` | Individual suites |
| `make data-download` | Incremental S3 download driven by the manifest; reads credentials from the environment |
| `make pipeline`, `make pipeline-sample` | Build bronze, silver, and gold (full or deterministic sample) |
| `make data-sample` | Regenerate the committed, bounded organizer data sample in `data_platform/sample/` (rule 5) |
| `make data-report`, `make analysis` | Data-quality report and per-workflow demand and prioritization analysis |
| `make seed` | Load the demo subset into PostgreSQL |
| `make train` | Train and register the learned components |
| `make eval` | Run the evaluation harness |
| `make openapi` | Export OpenAPI and regenerate the TypeScript client types |
| `make contracts` | Regenerate the JSON Schemas |
| `make docs-check` | Markdown lint and Mermaid validation |

## 11. Phase protocol

Every phase prompt in `kit/prompts/` runs under this protocol.

1. Sync, then read.
   - Phases commit directly to `main`, and teammates push to it too. If a remote is configured and the working tree is clean, run `git pull --ff-only` first. If the pull fails, or the tree is not clean, stop and tell the human. Never force-push, rebase, or merge over someone else's work.
   - Read this file, `docs/PROGRESS.md`, `docs/BACKLOG.md`, the phase prompt, and every file the prompt lists under "Read first".
2. Write a short plan to `docs/plans/phase-NN.md`:
   - files to create or change,
   - tests to add,
   - risks,
   - open questions.
3. If an open question blocks correctness (missing data, credentials, a product decision), record it under "Blocked" in `docs/PROGRESS.md` and stop. Do not guess.
4. Implement in small vertical increments. After each increment:
   - run the relevant tests,
   - fix failures,
   - commit with a Conventional Commit message.
5. Never leave required behavior unimplemented. Out-of-scope items go to `docs/BACKLOG.md`.
6. Before finishing, run `make check`. The phase is not done until it passes.
7. Update every document the prompt lists under "Docs", then add a phase entry to `docs/PROGRESS.md`:
   - what was done,
   - decisions and their ADR links,
   - how to verify,
   - known limitations,
   - the next phase.
8. End with a concise summary for the human: what changed, how to verify, and what needs human review.

## 12. Commit conventions

- **Branch:** phases commit directly to `main` (team decision). Pushing still happens only when the human asks (rule 3).
- **Format:** Conventional Commits, `type(scope): summary`. The summary is imperative, at most 72 characters, with no trailing period.
- **Types:** `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `build`, `ci`, `perf`, `security`.
- **Scopes:** `domain`, `policy`, `workflow`, `api`, `web`, `data`, `ml`, `evals`, `infra`, `docs`, `security`.
- **Body:** explains why the change was made, not just what changed.
- **Size:** one logical change per commit. Tests and docs go with the code they cover.
- **Attribution:** none. No AI trailers, no tool mentions, no emojis.

## 13. Definition of done

A phase is done only when all of the following are true:

- The behavior is implemented end to end for the phase scope, with no placeholders.
- Unit tests exist, plus integration tests for anything that touches I/O. Coverage gates hold.
- `make check` passes locally.
- The documentation listed in the phase prompt is written or updated, with Mermaid diagrams where the prompt asks for them.
- `docs/PROGRESS.md` has the phase entry.
- No secrets, emojis, or AI attribution exist anywhere in the diff or the commit messages.

## 14. Glossary

| Term | Meaning |
|---|---|
| Safe automated resolution | An eligible case reaches the correct, policy-compliant outcome without human intervention. Reported over all in-scope cases, plus the share where automation was attempted. |
| Containment | A case ends without transfer. Never reported alone as success. |
| Escalation quality | Required transfers happen with useful handoff context. Both missed and unnecessary transfers are counted. |
| Unsafe outcome | An unauthorized disclosure or action, or a materially incorrect outcome. Reported as counts with denominators. |
| Operating efficiency | p50/p95 latency and cost per attempted case and per successful resolution, with stated assumptions. |
| Execution record | The per-turn audit artifact: state, rule ids and versions, clause references, tool calls with verification results, model and prompt versions, latency, and cost. |
| Trust state | Per-session, append-only risk evidence. Its derived risk tier never decreases within a session. |
| Bound policy | A clause fetched deterministically by id for a workflow state, as opposed to one found by open retrieval. |
| Workflow registry | The set of supported workflows (`account_inquiry`, `card_support`, `dispute`, `credit`). Each maps its intents to one state machine; the router uses it to dispatch and to move a conversation between workflows. An intent outside it is out of scope. |
| Synthetic eligibility service | The deterministic `EligibilityPolicy` implementation that turns team-authored, synthetic `ELG` rules into an eligibility outcome with rule ids, reasons, and review flags. It never approves credit, and it is labeled synthetic wherever it appears. |
| Risk estimate | A predictive estimate from the `RiskEstimator` port: a probability with an uncertainty interval, a band, and a model version, trained on synthetic organizer data. It is one input to the synthetic eligibility service, never a decision, and never shown to customers or sent to a model. |
| Eligibility outcome | `indicatively_eligible`, `not_eligible`, `review_required`, or `insufficient_data`. There is no approved outcome by design. |
| Committed data sample | The bounded, deterministic extract of organizer data in `data_platform/sample/`, governed by rule 5. |
