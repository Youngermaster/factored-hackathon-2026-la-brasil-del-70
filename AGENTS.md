# AGENTS.md

The guide for every coding agent working in this repository (Codex, Cursor, GitHub Copilot, Gemini CLI, Claude Code, and any other), and for the people driving them. It tells an agent what the product is, how the code is laid out, which rules are enforced and by what, and how to make the common kinds of change without breaking anything.

## 1. Precedence and what to read first

When instructions disagree, the first one in this list wins:

1. The human who is driving the session.
2. [CLAUDE.md](CLAUDE.md), the normative working agreement. Despite its name it binds every agent and every contributor, not only Claude Code.
3. This file.
4. Package READMEs, plans, and older notes.

If this file disagrees with CLAUDE.md, CLAUDE.md is right and this file must be fixed.

Before editing anything, a non-Claude agent must read these CLAUDE.md sections:

| Section | Why |
|---|---|
| 2. Non-negotiable rules | No emojis, no AI attribution, git safety, no secrets, organizer data rules, no placeholders, never weaken checks |
| 5. Backend architecture rules | Layer direction, repositories, decorators, composition root, policy, prompts, isolation |
| 6. Frontend architecture rules | Layers, composition, state, API access, security, i18n |
| 7. Security standards | Sessions, CSRF, authorization, input limits, prompt injection, logging, audit |
| 8. Testing rules | Unit, integration, contract, property and web tests, coverage gates |

Then read the README of every package the task touches (links in section 5).

## 2. What the product is

An AI-first banking customer-service system for the Factored AI and Data Hackathon 2026 ([brief](docs/organizer/BRIEF.md)). Customers of a synthetic bank in Mexico, Colombia, and Argentina chat in Spanish or Portuguese. Four workflows run on one shared engine:

| Workflow id | What the system may do |
|---|---|
| `account_inquiry` | Read only: balances, payment status, statement summaries, always stating the as-of date of the data |
| `card_support` | Card status and a protective card block (confirmation, step-up, verified read-back); unblock and replacement go to a human |
| `dispute` | Open a dispute case (confirmation, verified read-back), optional protective block, dispute status |
| `credit` | Synthetic catalog answers, an indicative result from the synthetic eligibility service, an application intake for human review; never a lending decision |

Everything else gets a clarifying question, a clause-backed abstention, or a structured handoff to a human.

Design thesis: **the language model understands, deterministic code decides, and evidence proves it.** In practice:

- Policy is data under `policies/`, evaluated by pure rule functions; every decision names its rule ids and clause versions.
- Identity comes from a trusted test session (mock identity service with one-time codes). The model never receives or chooses customer identifiers.
- Writes are idempotent and are reported to the customer only after a read-back verifies them.
- Every turn leaves an execution record. Hidden chain-of-thought is never stored or shown.
- Handoffs carry the request, verified facts, actions taken, evidence, and open questions, never a raw transcript.
- Credit keeps conversation, risk estimate, and eligibility behind separate ports (`RiskEstimator`, `EligibilityPolicy`). The model never sees the risk estimate or the credit profile and never states or implies approval.

**Scope is settled.** All four workflows are automated as built. [ADR 0025](docs/adr/0025-tuesday-account-inquiry-mvp-and-observability.md) proposed a narrower "Tuesday MVP" (only `account_inquiry` automated, the other workflows sent to a mock human agent, plus an assistant profile and Langfuse traces). The human decided the build does not follow that scope (pending action 32 in [PROGRESS.md](docs/PROGRESS.md)), and the teammate branch `feat/privacy-safe-langfuse-api` stays unmerged. Do not reopen the decision, and do not build ADR 0025's mock agent, assistant profile, or Langfuse integration unless the human asks.

## 3. Current state

[docs/PROGRESS.md](docs/PROGRESS.md) is the source of truth for status: its "Current state" table, its "Pending human actions" list, and the phase log. [docs/BACKLOG.md](docs/BACKLOG.md) holds deferred work with the phase that owns it. Read both before starting; do not trust a status line copied anywhere else, including here.

As of this file's last update:

| Item | State |
|---|---|
| Phases 00 to 13 | Done (data platform, policy, grounding, LLM gateway, engine and four workflows, learned models, API, web app with chat, glass box, agent inbox, evaluation view) |
| Phase 14a | Done: the evaluation harness (`bank-eval`, 332 test and 122 dev scenarios) |
| Phase 14b | Done: the frozen test run on the local Ollama `qwen2.5:7b-instruct`, published; the cassettes are committed |
| Phase 15 | Done: OpenTelemetry traces and metrics, the degradation ladder, the chaos suite, alerts, the local load test |
| Phase 16 | Done: security review and the single-host production stack (`deploy/`), verified locally with TLS and the local model |
| Phase 17 | Done: the final documentation and audit (README, LIMITATIONS, architecture views, the brief traceability matrix, the submission package in `docs/submission/`), the data-use record, no license ("All rights reserved"), the demo-guide fixes |
| Remaining (human) | Choose the host and deploy, fill `deploy.url` in `slides/data/metrics.yml`, export the slides, record the video, make the repository public, send the email ([docs/submission/SUBMISSION.md](docs/submission/SUBMISSION.md)) |
| Submission deadline | 2026-10-05 |

Runtime defaults (from [.env.example](.env.example)): `LLM_PROVIDER=fake` (no model call; workflows use deterministic fallbacks), `WORKFLOW_ROUTER=keyword@1`, `WORKFLOW_RESOLVER=rules@1`, `WORKFLOW_RISK_ESTIMATOR=score_band@1`, `DEMO_MODE=true`. Learned components exist but are not the defaults.

## 4. Quick start on a fresh machine

### Prerequisites

| Tool | Version and source |
|---|---|
| uv | 0.11.17 or later; it installs Python 3.12 from `.python-version` |
| Node.js | 24.15 or later, below 25 (`engines` in `apps/web/package.json`); `.nvmrc` says `24`, so `nvm install` then `nvm use` |
| pnpm | 10.33, pinned by `packageManager` in `apps/web/package.json` |
| Docker | With Compose v2; PostgreSQL for the dev stack and for integration tests |
| pre-commit, gitleaks | Installed on the machine; `make setup` installs the hooks |
| GNU make | On Windows use WSL2 |

### Steps

```bash
nvm use                                   # Node from .nvmrc; non-interactive shells may need `nvm use 24`
make env                                  # creates .env with fresh dev secrets (only when .env is absent)
# or: cp .env.example .env                # also works; its dev-only secrets are refused in production
make setup                                # Python and web dependencies, git hooks
make up                                   # PostgreSQL (compose); PROFILES="api web" also starts both apps in containers
make db-upgrade                           # Alembic migrations as the owner role
make pipeline                             # bronze, silver, gold from the committed sample: offline, no credentials
make seed                                 # demo personas plus up to SEED_CUSTOMERS (200) customers from gold; also migrates
```

`make seed` reads gold, so it fails until `make pipeline` (or a copied warehouse under `data/`) has produced it.

Run the API and the web app on the host (the demo persona picker needs `VITE_DEMO_MODE=true`):

```bash
DEMO_MODE=true uv run --frozen uvicorn bank_agent.asgi:create_app --factory --reload   # API on :8000
VITE_DEMO_MODE=true pnpm --dir apps/web run dev                                         # web on :5173
```

Sign in at `http://localhost:5173` with a persona id from [docs/demo/personas.md](docs/demo/personas.md) (for example `crd-mx-two-cards`, or `agent-demo-01` for the agent console). With `DEMO_MODE=true` the one-time code is shown on screen, labeled as a demo. Writes such as a card block ask for a fresh code (step-up).

Before calling any change done:

```bash
make check                                # every gate; needs Docker, never reads .env
```

A verified, timed walkthrough of every local path (dev stack, browser, local model, evaluation, production stack, slides, gates) with its troubleshooting is [docs/submission/LOCAL-RUN.md](docs/submission/LOCAL-RUN.md).

The production stack (Caddy with TLS, two API workers, PostgreSQL with a non-superuser owner, the jobs) also runs locally in its local TLS mode: [deploy/README.md](deploy/README.md), "Run the production stack locally".

Opt-in local model (never in `make check` or CI): with Ollama serving `qwen2.5:7b-instruct`, `make api-local-llm` runs the API through LiteLLM, and `LLM_PROVIDER=litellm LLM_PRIMARY_MODEL=ollama/qwen2.5:7b-instruct LLM_API_BASE=http://localhost:11434 make llm-smoke` runs the fixture prompts (a bare `make llm-smoke` reads the fake provider from `.env` and stops). See `.env.example` and [docs/architecture/llm-gateway.md](docs/architecture/llm-gateway.md).

### Data sources

| Source | What it is | How |
|---|---|---|
| `sample` (default) | The committed, bounded, pseudonymized extract in `data_platform/sample/`; works offline with no credentials | `make pipeline`, then `make seed` |
| `s3` | The full organizer delivery (13 tables, about 23.5 million rows) downloaded into `data/` (gitignored) | Organizer S3 values in `.env`, then `make data-download` and `make pipeline DATA_SOURCE=s3` |
| `local` | Organizer CSVs already on disk | `make pipeline DATA_SOURCE=local LOCAL_DIR=data` |

S3 credentials come only from the organizer, through the team. They are never committed, pasted into prompts, issues, or chats, or printed. The organizer data dictionary PDF contains credentials and must never be committed. Only the governed sample in `data_platform/sample/` may be in git (CLAUDE.md rule 5). The `download-organizer-data` and `setup-postgres-data` skills (section 11) walk through both paths.

## 5. Repository map

| Path | Content |
|---|---|
| `services/api/` | Python package `bank_agent` ([README](services/api/README.md)): the FastAPI service with a hexagonal core |
| `apps/web/` | Vite, React 19, TypeScript client ([README](apps/web/README.md)): customer chat, glass box, agent inbox, evaluation view |
| `data_platform/` | `bank-data` ([README](data_platform/README.md)): ingestion, Pandera contracts, dbt-duckdb bronze, silver, gold, reports, EDA, the seed, and the committed sample in `data_platform/sample/` |
| `ml/` | `bank-ml` ([README](ml/README.md)): intent router, transaction resolver, and credit risk estimator training, evaluation, promotion |
| `evals/` | `bank-evals` ([README](evals/README.md)): scenario sets, systems under test (H, B0, B1, P), graders, statistics, reports, cassettes |
| `policies/` | The synthetic policy pack ([README](policies/README.md)): clauses in es, pt, en, bindings, action matrix, credit catalog, eligibility messages, version lock |
| `contracts/` | JSON Schemas generated from Pydantic models and the committed `contracts/openapi.json` ([README](contracts/README.md)) |
| `deploy/` | The production stack for one VM (`compose.prod.yml`, `prod.sh`, Caddy, the smoke test, production PostgreSQL roles) with the deployment guide for Lightsail, EC2, and Azure, plus the development stack's role bootstrap and observability configuration ([README](deploy/README.md)) |
| `docs/` | Architecture, ADRs, workflows, API, security, data, models, evaluation, design, demo, submission, plans, progress ([index](docs/README.md)) |
| `README.md`, `LIMITATIONS.md` | The judge-facing summary and the honest limits; keep their numbers identical to `docs/evaluation/results.md` |
| `scripts/` | Repository checks (`scripts/checks/`), git hooks (`scripts/hooks/`), contract and OpenAPI export, env generation, the LLM smoke script |
| `slides/` | The pitch deck ([README](slides/README.md)): a standalone Slidev package, outside the uv workspace and outside `make check` |
| `skills/` | Tool-agnostic agent skills for this repository (section 11) |
| `.claude/` | Claude Code settings and the design skills CLAUDE.md names (`design-taste-frontend`, `minimalist-ui`); other agents may read these files as plain Markdown |
| `.github/` | CI workflow (`.github/workflows/ci.yml`) and the pull request template |
| `data/` | Gitignored: raw downloads, warehouses, model artifacts, labeling files, embeddings |
| `kit/` | Gitignored and private to the technical lead: phase prompts and organizer PDFs. Teammates do not have it, so never depend on a `kit/` prompt; ask the human for the phase goal instead |

Key subpackages of `services/api/src/bank_agent/`:

| Path | Content |
|---|---|
| `domain/` | Pure entities, value objects (`Money` with `Decimal` and currency), enums, typed errors, `ToolName` |
| `ports/` | Protocol interfaces, including repositories in `ports/repositories/` |
| `policy/` | Pack loader, pure rules in `policy/rules/`, evaluator, synthetic eligibility, approval-wording lexicon |
| `application/` | `engine/` (state machine, router, gate, templates), `workflows/<id>/`, `tools/`, `grounding/`, `understanding/`, `conversations/`, `agent/`, `identity/`, `preferences/` |
| `adapters/` | `persistence/{postgres,duckdb,memory}`, `llm/`, `retrieval/`, `identity/`, `models/`, `policy/`, `prompts/`, `telemetry/`, `evaluation/`, `system/` |
| `api/` | FastAPI app, routers, request and response schemas, CSRF, cookies, rate limits, problem details |
| `bootstrap/` | Settings (the only module that reads the environment) and `container.py`, the composition root |
| `prompts/` | Versioned prompt files, `<prompt_id>/<version>.md` |
| `testing/` | Test doubles (`FakeLLM`, fixed clock, deterministic ids); production code never imports them |

Web layers under `apps/web/src/`: `app/` (providers, routes, composition root), `pages/`, `features/<name>/`, `entities/`, `shared/` (UI primitives, API client and generated types, i18n, config, lib), `test/` (setup, MSW fakes).

## 6. Architecture rules and what enforces them

A failing check means the code is in the wrong place or breaks a rule. Move or fix the code; never loosen the check.

### Backend

| Rule | Enforced by |
|---|---|
| Imports flow inward only: `domain` <- `ports` <- `policy` <- `application` <- `adapters` <- `api` and `bootstrap` | import-linter contracts in `pyproject.toml` (`make lint`, `uv run --frozen lint-imports`); seven contracts, including "pure core has no framework or I/O imports", "production code never imports the test doubles", and the evaluation harness separation |
| `api` and `bootstrap` never import each other; the API receives services through the `ServiceProvider` Protocol | import-linter; wiring lives in `services/api/src/bank_agent/asgi.py` and `services/api/src/bank_agent/cli.py` |
| `bootstrap/container.py` is the only module that constructs concrete adapters; FastAPI dependencies, CLIs, and the evaluation harness resolve from it | Code review; the import contracts |
| Every external dependency sits behind a Protocol in `ports/`; every adapter passes the shared contract suite for its port in `services/api/tests/contracts/` | Contract tests, run against the memory and PostgreSQL backends |
| Cross-cutting behavior (retry, timeout, circuit breaker, budget, tracing, redaction, caching) is a decorator implementing the same port, stacked in the composition root | Code review; see [docs/architecture/llm-gateway.md](docs/architecture/llm-gateway.md) |
| Policy is data: rule parameters and clause text live in `policies/`; rules are pure functions registered by id; every `Decision` names rule ids and clause versions | The pack loader refuses a pack that does not bind a rule or lacks a parameter; `policies/versions.lock.yaml` refuses changed text without a version bump |
| Prompts are versioned files; code references them by id and version; published versions are immutable; inputs are an allowlist | The prompt registry (load-time checks) and `services/api/tests/unit/adapters/test_prompt_registry.py` |
| Models are ports selected by `name@version` or alias through settings; swapping one never changes workflow code | `bootstrap/models.py`, contract tests in `test_model_ports_contract.py` |
| `Money` uses `Decimal` with an explicit currency, never floats; time comes from a `Clock` port, ids from an `IdGenerator` port | Domain tests and Hypothesis property tests |
| Only `bootstrap/` reads the environment; production refuses default or empty secrets, `DEMO_MODE=true` without `ALLOW_PUBLIC_DEMO_MODE=true`, the owner password in the API process, and the in-process rate limiter | `bootstrap/settings.py` and its unit tests |
| Domain errors map to RFC 9457 problem details in one place; internals never leak | `api/domain_problems.py`, `api/problems.py`, and API tests |
| mypy strict, ruff, bandit | `make typecheck`, `make lint` |

### Frontend

| Rule | Enforced by |
|---|---|
| Imports flow downward only: `pages` -> `features` -> `entities` -> `shared`; a feature is imported only through `features/<name>/index.ts` | ESLint boundary rules in `apps/web/eslint.boundaries.js`, proven by `apps/web/tooling/boundaries.test.ts` |
| Server state only in TanStack Query; local UI state in components; feature-scoped shared state in context with `useReducer`; Zustand only with a written justification in `docs/frontend/state.md` (none today) | Code review; [docs/frontend/state.md](docs/frontend/state.md) |
| No prop drilling beyond two levels; compound components and slots over boolean props | Code review |
| API types are generated from OpenAPI into `apps/web/src/shared/api/generated/schema.d.ts`; never edit that file; no `any` | `apps/web/tooling/api-types.test.ts` (stale types fail); ESLint `@typescript-eslint/no-explicit-any` |
| Every user-facing string lives in `apps/web/src/shared/i18n/locales/{es,pt,en}.json` | `apps/web/tooling/no-hardcoded-strings.test.ts` and the locale parity test |
| Design tokens only, one icon set (Phosphor), no emojis, no em dashes in UI copy, WCAG 2.2 AA | [docs/design/DESIGN.md](docs/design/DESIGN.md); vitest-axe on every page in both themes; the emoji guard |

### Security

| Rule | Enforced by |
|---|---|
| No tokens in `localStorage` or `sessionStorage`; the session is an `HttpOnly` cookie; the CSRF token lives in memory | ESLint restricted globals in `apps/web/eslint.config.js` (only display preferences in `shared/lib/preferences.ts` may use web storage) |
| Never `dangerouslySetInnerHTML`; model output renders as plain text; no inline scripts (strict CSP) | ESLint `no-restricted-syntax` rule |
| CSRF: signed double-submit token (`X-CSRF-Token`) on every state-changing request | `endpoint(..., changes_state=True)` in `api/dependencies.py`; API tests; [ADR 0031](docs/adr/0031-cookie-sessions-with-signed-double-submit-csrf.md) |
| Every route declares roles and a rate class; request models reject unknown keys and set maximum lengths; response models are allowlists | `endpoint(...)`, `RequestModel` and `ResponseModel` in `api/schemas/base.py`; the OpenAPI contract test |
| Cross-customer access returns 404, never 403 | API and tool integration tests |
| Row-level security is forced on customer tables; the application role owns nothing and has no `BYPASSRLS`; the RLS context is set inside each transaction | `services/api/tests/integration/test_row_level_security.py`, `test_database_roles.py`; [docs/security/data-isolation.md](docs/security/data-isolation.md) |
| Tools the model can influence never accept customer identifiers; tools come from a per-state allowlist | Tool contract suites; [docs/security/prompt-injection.md](docs/security/prompt-injection.md) |
| Only the fields a prompt needs reach a model; no document numbers, names, emails, phones, addresses, credit profile, or risk estimate | Prompt input allowlists, the forbidden-variable check, redaction in `adapters/llm/redaction.py` |
| Execution records and audit events are append-only at the database level | `services/api/tests/integration/test_schema_guards.py` |
| No secrets in the repository; never read or print `.env` (use `make env-check`) | gitleaks in pre-commit and CI |

## 7. Recipes

Each recipe lists the minimum set of files that must change together. The linked README has the detail. Every recipe ends with the relevant tests, then `make check`, then the docs that describe the change, in the same pull request.

### Add or change a policy clause or rule

Detail: [policies/README.md](policies/README.md), [policy package README](services/api/src/bank_agent/policy/README.md).

1. Edit or add the clause in all three languages together: `policies/clauses/<family>/<CLAUSE-ID>.{es,pt,en}.md`. Ids, version, jurisdiction, parameters, bound rules, and placeholders must match across the three files.
2. Changing an existing clause: raise `version` by one in all three files; move the old files to `policies/clauses/<family>/superseded/<CLAUSE-ID>@<old version>.<lang>.md` to keep old execution records resolvable.
3. New rule: a pure function in the matching module of `services/api/src/bank_agent/policy/rules/`, registered with `@RULES.rule("FAM.name", version=..., reasons=..., params=..., missing_facts=...)`, with unit tests for boundaries and a missing fact. Bind a clause to it (`bound_rules`) and bind the clause to states in `policies/bindings.yaml`. Write actions are rows in `policies/matrix.yaml`.
4. `make policy-lock` (refuses changed text without a version bump), then `make policy-catalog` (regenerates `docs/policy/catalog.md`).
5. Tests: `uv run --frozen pytest services/api/tests/unit/policy services/api/tests/integration/policy`. Golden texts change only with a reviewed wording change.
6. Credit clauses (CRE, ELG) and every credit text must contain no approval wording in any language, even negated (`policy/lexicon.py`).

### Add or change a tool

Detail: [application README](services/api/src/bank_agent/application/README.md).

1. Add the name to `ToolName` in `services/api/src/bank_agent/domain/actions.py`. It appears in the execution record schema, so this is a contract change (see "Change a contract schema").
2. Implement it as a `ToolCalls` method in `services/api/src/bank_agent/application/tools/` doing its work inside `_run` (one unit of work, one audit event); add it to `SessionToolset` and the failure injector. The customer comes from the session, never from a model argument.
3. A write also needs an idempotency rule, a `WriteVerifier` read-back, a `PlannedWrite`, an action policy state allowed by `policies/matrix.yaml`, and step-up where the matrix says so.
4. Add it to the allowlist of each state that needs it.
5. Cover it in `services/api/tests/contracts/test_read_tools_contract.py` or `test_write_tools_contract.py`, so it runs on memory and PostgreSQL.

### Add a workflow state

1. Add the canonical state name to the workflow's `WorkflowDescriptor.states` in `services/api/src/bank_agent/domain/workflow_catalog.py`.
2. In `services/api/src/bank_agent/application/workflows/<id>/definition.py`, add a `StateSpec` (kind, tool allowlist, and for writes `action_policy_states`) and the state's exits in the transition table. Write the async handler `(TurnContext) -> Step`: reads only through `ctx.tools`, decisions through `decide.evaluate` (`application/engine/decide.py`), replies from templates.
3. Bind it in `policies/bindings.yaml` if it needs its own rules or clauses (and `policies/matrix.yaml` for writes). The registry refuses a definition whose bindings and matrix disagree.
4. Templates in es, pt, and en under `services/api/src/bank_agent/application/engine/templates/`, with a golden entry (`UPDATE_TEMPLATE_GOLDEN=1` regenerates; review the diff).
5. Scenario tests in es and pt in `services/api/tests/integration/workflows/`, and the state tables and diagrams on the workflow's page in `docs/workflows/`.

### Add a prompt or a prompt version

Detail: [prompts README](services/api/src/bank_agent/prompts/README.md).

1. Never edit a published version. Copy the latest `services/api/src/bank_agent/prompts/<prompt_id>/<n>.md` to `<n+1>.md` and add a changelog entry in its front matter.
2. Structured output: add the model to `domain/llm_outputs.py` and to `OUTPUT_MODELS`.
3. Mark inputs from customers or stored records `untrusted: true`. Never declare an input that carries identifiers, the credit profile, or a risk estimate (loading fails).
4. Reference it from code as `PromptRef(prompt_id=..., version=...)`; script it in `FakeLLM` for tests; add cassettes under `evals/cassettes/<prompt_id>/<version>/` ([cassettes README](evals/cassettes/README.md)).

### Add an adapter, a model, or a new port

Detail: [adapters README](services/api/src/bank_agent/adapters/README.md), [ports README](services/api/src/bank_agent/ports/README.md), [ml README](ml/README.md).

1. New port: a Protocol in `services/api/src/bank_agent/ports/` with a docstring on preconditions, errors, and isolation, plus a shared contract suite in `services/api/tests/contracts/`.
2. Adapter: implement the Protocol under `adapters/<area>/<technology>/`; register it as a backend in `services/api/tests/bank_agent_contracts.py` so the contract suite runs against it; select it by name from settings in `bootstrap/container.py` (persistence in `bootstrap/persistence.py`, models in `bootstrap/models.py`, the language model stack in `bootstrap/llm.py`).
3. Learned model: follow the six steps in the ml README (adapter that loads a digest-checked JSON artifact, `fit_*`, register, evaluate, select, promote). Add a model card in `docs/models/`. Never change the default without an end-to-end evaluation.
4. A new setting goes in the matching class in `bootstrap/settings.py` and in `.env.example` in the same commit, with a production rule if it is a secret.

### Add an API route

Detail: [api package README](services/api/src/bank_agent/api/README.md), [docs/api/README.md](docs/api/README.md).

1. Add the route in `services/api/src/bank_agent/api/routers/` with `**endpoint(rate=..., roles=..., changes_state=..., operation_id=...)` and a session parameter from `role_dependency` for signed-in roles; include a new router in `api/app.py`.
2. Request models extend `RequestModel` (unknown keys rejected, explicit maximum lengths); response models extend `ResponseModel` and list only the fields a client may see. Customer and staff views are separate classes.
3. Return 404 for another customer's resource. New domain errors go in `domain/errors.py`; map them only if clients must act differently.
4. `make openapi` regenerates `contracts/openapi.json` and `apps/web/src/shared/api/generated/schema.d.ts`. Commit both.
5. Add the row to the endpoint catalog in `docs/api/README.md` (a test compares it with the code) and integration tests through the ASGI transport in `services/api/tests/integration/api/`.

### Add a UI feature

Detail: [apps/web/README.md](apps/web/README.md), [features README](apps/web/src/features/README.md), [docs/frontend/features.md](docs/frontend/features.md).

1. Create `apps/web/src/features/<name>/` with `api/` (TanStack Query hooks over `useApi()` and `queryKeys`), `model/`, `ui/`, and an `index.ts` that exports only the public surface.
2. Pages under `apps/web/src/pages/` compose features and hold no business logic; register routes in `apps/web/src/app/routes.tsx`.
3. Add every string to `es.json`, `pt.json`, and `en.json` in `apps/web/src/shared/i18n/locales/` together. Format money, dates, and numbers with the `useFormat` helpers.
4. Add typed MSW fakes in `apps/web/src/test/msw/` (built from `apps/web/src/test/msw/api.ts`) and an integration test per feature with `renderApp` from `apps/web/src/test/app.tsx`; add the page to the vitest-axe checks in `apps/web/src/app/a11y.test.tsx` or `a11y-surfaces.test.tsx`.
5. New shared primitives go in `apps/web/src/shared/ui/` and `docs/frontend/components.md`; design decisions in `docs/design/DESIGN.md`.

### Add a database migration

Revisions live in `services/api/src/bank_agent/adapters/persistence/postgres/migrations/versions/` as `NNNN_short_name.py` with `revision = "NNNN"` and `down_revision` set to the previous number.

1. Check the latest revision on an up-to-date `main` first (`ls` that folder after `git pull --ff-only`). Two branches that both add the next number produce two Alembic heads.
2. Migrations only move forward: never edit a merged revision; write a new one with a working `downgrade()`.
3. A new customer-data table needs `ENABLE` and `FORCE ROW LEVEL SECURITY` and policies keyed on the session context (see `0006_row_level_security.py` and `0009_tuesday_chat_and_profile.py`), plus explicit grants to the application role (see `0007_grants_and_evaluation.py`), only the privileges the service needs. The application role gets no `DELETE` or `TRUNCATE` anywhere, and audit tables stay append-only.
4. Update the PostgreSQL repository and mappers, the memory adapter, and the shared contract suite; extend `services/api/tests/integration/test_row_level_security.py` for new tables or policies.
5. Update the tables in [docs/security/data-isolation.md](docs/security/data-isolation.md). Anyone with an existing database runs `make db-upgrade`.

### Change a contract schema

Detail: [contracts/README.md](contracts/README.md) (versioning, deprecation, changelog).

1. Change the Pydantic model. Additive changes are a minor bump (new optional input field marked `AddedIn`, new output field, new enum value); anything that can invalidate a valid document or change its meaning is a major bump with a new file.
2. Bump the version in `scripts/generate_contracts.py` and the model's default `schema_version` (a test checks they match).
3. `make contracts` regenerates `contracts/schemas/*.json`; a unit test fails when a committed schema is stale.
4. Add the changelog row in `contracts/README.md` and commit the model, the schemas, and the consumers together.

### Add an ADR

1. Find the next free number in [docs/adr/README.md](docs/adr/README.md) on an up-to-date `main`, and check open branches and pull requests too. Numbers have collided three times (0025, the EDA records renumbered to 0032 and 0033, the seed record renumbered to 0034). 0017 stays reserved and unused; the next free number is 0036.
2. Write `docs/adr/NNNN-short-title.md` in MADR form: context, at least two real options, decision, consequences.
3. Add the row to the table in `docs/adr/README.md` and the entry in `docs/README.md` in the same commit.
4. Records are never rewritten; a later record supersedes an earlier one and both link to each other.

### Add evaluation scenarios

Detail: [evals/README.md](evals/README.md), [docs/evaluation/plan.md](docs/evaluation/plan.md), [docs/evaluation/methodology.md](docs/evaluation/methodology.md).

1. Add the situation to `evals/src/bank_evals/scenarios/family_data/<workflow>.yaml` with at least two phrasings, labels taken from the policy documents, and facts in braces from `evals/src/bank_evals/scenarios/facts.py`. New persona roles or records go in `evals/src/bank_evals/world/records.py`, named symbolically; never copy organizer records.
2. `make eval-scenarios` regenerates both splits deterministically and runs lint, leakage guards, and the test set lock. Changing the locked test split needs `uv run --frozen bank-eval scenarios generate --relock` and a recorded reason in the phase log; never tune on the test split.
3. `make eval-smoke` must still pass (the CI smoke suite, no model).
4. Coordinate with whoever runs the live evaluation before touching `evals/` while a run is in progress (session 14b).

## 8. Testing and quality gates

`make check` runs, in order: `make lint` (ruff, ruff format check, import-linter, bandit, ESLint, Prettier), `make typecheck` (mypy strict, `tsc -b`), `make test-unit` and `make test-integration` with coverage, the per-directory coverage gates, `make test-web`, `make docs-check`, the data sample bound check, `bank-data codegen --check`, the emoji guard, the AI-attribution guard, and gitleaks over the history. It needs Docker running (integration tests start their own PostgreSQL through testcontainers) and never reads `.env`. Expect it to take more than ten minutes.

| Target | Runs |
|---|---|
| `make test-unit` | Python unit tests; network disabled by pytest-socket |
| `make test-integration` | Python integration tests against real PostgreSQL (Docker) |
| `make test-web` | Vitest with coverage |
| `make docs-check` | markdownlint, Mermaid parsing, and the check-script tests; needs `apps/web/node_modules` |
| `make security` | pip-audit, `pnpm audit --prod --audit-level high`, bandit, gitleaks, hadolint, shellcheck, production compose validation (Docker needed; network for the audits) |
| `make images`, `make scan-images` | Build the production images; trivy (fixable HIGH and CRITICAL fail) and CycloneDX SBOMs |
| `make smoke`, `make csp-check` | Smoke test and browser CSP check of a deployed stack (`SMOKE_URL=https://...`) |
| `make eval-smoke` | 12-scenario smoke suite with a scripted client, no model |
| `make submission-check` | The pre-submission gates (`make check`, `make security`, `make eval-smoke`, the slides verify, `make docs-check`), then the remaining human steps |
| `make format` | Applies ruff, ESLint, and Prettier fixes |

Narrow runs while iterating: `uv run --frozen pytest services/api/tests/unit/<area> -q`, `pnpm --dir apps/web exec vitest run <path>`.

Coverage gates (`[tool.bank.coverage-gates]` in `pyproject.toml`, checked by `scripts/checks/check_coverage_gates.py`): 90% for `domain`, `ports`, `policy`, `application`, and `testing`; 80% for `adapters`, `api`, `bootstrap`, `data_platform/src`, `ml/src`, and `evals/src`; 70% for `apps/web/src/features/**`.

Rules:

- Never disable, skip, xfail, or weaken a test, linter, type check, coverage gate, or security check. Fix the cause.
- Tests never call a live model. Use `FakeLLM` or cassettes. Live runs (`make llm-smoke`, `make api-local-llm`, `EVAL_LLM=record`) are opt-in and never part of `make check` or CI.
- Test names describe behavior (`test_rejects_dispute_after_window_closes`). Every bug fix adds a regression test.
- Fixtures are small, synthetic, team-made, and labeled as fixtures; never organizer records.
- Say plainly when a check could not run (for example no Docker) instead of reporting a pass.

## 9. Pitfalls this project has already paid for

| Pitfall | What to do |
|---|---|
| A plain `uv sync` is exact: it removes every extra it was not told to install. `make setup` itself runs `uv sync --all-packages --extra eda-ui --frozen`, which removes the optional `ml` and `litellm` extras if they were installed | Run commands through `uv run --frozen ...` (it syncs inexactly). To add an extra without removing others: `uv sync --inexact --all-packages --extra <name> --frozen` |
| Non-interactive shells (agent terminals, hooks, CI-like scripts) do not load nvm, so an older default Node (below 24.15) may run | `nvm use 24` first, or put the Node 24 `bin` directory first on `PATH` |
| An env file reads everything after `NAME=` as the value, so `POLICY_DIR=   # default` sets `POLICY_DIR` to the comment text | Keep comments on the line above an empty value, as `.env.example` does. Diagnose with `make env-check`, never by reading `.env` |
| A second checkout on the same machine (a clone or a worktree) shares the dev compose project `bank-agent`: its `make up` takes over the first checkout's PostgreSQL container and volume | In the second checkout's shells, `export COMPOSE_PROJECT_NAME=bank-agent-<name> POSTGRES_PORT=<free port>` before `make up`, `make db-upgrade`, `make seed`, and the API ([LOCAL-RUN.md](docs/submission/LOCAL-RUN.md)) |
| The PostgreSQL volume keeps the passwords it was created with; a new `.env` from `make env` has different ones | Keep the passwords the volume was created with. Never run `docker compose down --volumes` without the human's approval: it erases the local database |
| ADR numbers and Alembic revision numbers collide when branches land in parallel | Check the next free number on an up-to-date `main` and in open pull requests right before committing (section 7) |
| `docs/PROGRESS.md`, `docs/BACKLOG.md`, `docs/README.md`, `docs/adr/README.md`, `.env.example`, and the `Makefile` are merge-conflict hotspots | Append rather than reorder; when resolving a conflict keep both sides, then run `make docs-check` |
| The `**/data/*` rule in `.gitignore` hides the contents of any folder named `data`, at any depth. Only `docs/data/`, `evals/data/`, and `slides/data/` have exceptions | Do not name a new source folder `data`; check with `git check-ignore -v <path>` and `git status` that new files are tracked |
| pre-commit runs gitleaks, the emoji guard, the AI-attribution strip on the commit message, ruff, ESLint, Prettier, and a 500 KB file limit; CI runs gitleaks and the attribution guard over the full history | Fix what the hook reports. Never `git commit --no-verify`. An attribution trailer that reaches a shared branch cannot be removed without rewriting history |
| Some agents add `Co-authored-by` or "Generated with" lines by default | Turn that off in the agent's settings before the first commit |
| Demo writes persist: a charge can be disputed once per database; `make seed` restores blocked cards but not opened cases or intakes | Run `make seed` on a fresh compose volume before recording a demo or video; run `make db-upgrade` on an existing database after new migrations |
| The committed sample has no customer for four of the sixteen customer personas (`acc-co-payments`, `acc-ar-similar-transfers`, `dsp-ar-repeat-complainer`, `dsp-mx-similar-purchases`); signing in as one fails on a sample seed | Keep the demo guide on the twelve sample personas (`data_platform/tests/unit/test_demo_guide_personas.py` checks it); drive any new guide message through the API on a fresh sample seed before listing it ([docs/demo/personas.md](docs/demo/personas.md)) |
| Rotating `SESSION_SECRET` changes the keys derived for identity lookups and one-time codes | Run `make seed` again after rotating it (on the VM: `deploy/prod.sh seed`) |
| Production settings are validated per process: the API refuses the owner password, `DEMO_MODE` without `ALLOW_PUBLIC_DEMO_MODE`, and the in-process rate limiter; owner jobs need `load_settings(owner=True)` | A new production setting goes in the right branch of `production_problems` in `bootstrap/settings.py`, in `.env.example`, in `deploy/.env.production.example`, and in the service's `environment` in `deploy/compose.prod.yml` (`tests/unit/test_deploy_config.py` checks the template) |
| The production stack in a worktree or next to the dev stack clashes on ports or project names | Run it with its own project name and ports (`PROJECT=... ENV_FILE=... deploy/prod.sh ...`, `HTTP_PORT=8080 HTTPS_PORT=8443`); it publishes no database port. Remove it with `docker compose ... -p <project> down --volumes` when done |
| A strict CSP breaks a library that injects `<style>` elements or inlines assets | Keep the nonce path (`shared/lib/csp-nonce.ts`) and `assetsInlineLimit: 0`; run `make csp-check` against a deployed stack before loosening anything |
| Generated files drift when edited by hand | Regenerate instead: `make openapi` (OpenAPI and web types), `make contracts` (JSON Schemas), `make policy-lock` and `make policy-catalog` (policy lock and catalog), `make data-codegen` (dbt sources and contracts), `bank-eval publish` (evaluation results) |
| `kit/` exists only on the technical lead's machine | Never reference or depend on a `kit/` prompt; ask the human for the goal and acceptance criteria |

## 10. Collaboration

**Branches and pull requests.** Phase sessions run by the technical lead commit to `main` (CLAUDE.md section 12). Teammate work lands through pull requests from a branch off `main`; existing branches are named `<type>/<short-topic>` (for example `feat/tuesday-chat-persistence`, `docs/download-organizer-data-skill`). Start from a clean tree with `git pull --ff-only`. Push only when the human asks. For any GitHub operation follow [skills/github-collaboration/SKILL.md](skills/github-collaboration/SKILL.md), and fill in [.github/pull_request_template.md](.github/pull_request_template.md).

**Commits.** Conventional Commits, `type(scope): summary`, imperative, at most 72 characters, no trailing period, a body that explains why. Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `build`, `ci`, `perf`, `security`. Scopes: `domain`, `policy`, `workflow`, `api`, `web`, `data`, `ml`, `evals`, `infra`, `docs`, `security` (the history also uses `slides` for the pitch deck). One logical change per commit, with its tests and docs.

**Never:** AI attribution in commits, pull requests, docs, or code comments; emojis anywhere; `git commit --no-verify`; force-push or history rewrites on shared branches; `git reset` over someone else's work; changing `git config user.*`.

**Docs travel with code.** Update the README of the package you changed, the workflow page, the API catalog, or the ADR index in the same pull request. Out-of-scope findings go to `docs/BACKLOG.md` with the reason and the owning phase. Questions that block correctness (a product decision, credentials, a dependency over about 50 MB) go to the human; do not guess.

**Who does what** (from [docs/plans/kickoff-notes.md](docs/plans/kickoff-notes.md) and [ADR 0000](docs/adr/0000-team-alignment-and-hackathon-strategy.md)):

| Person | Role |
|---|---|
| Young | Technical lead: repository setup, core architecture, stack, agent integration, phase sessions |
| Miguel Correa | Project manager and AI engineer: project management, ADR and pull request drafting, alignment with the challenge criteria |
| David Fonseca | Developer and analyst: dataset analysis at kickoff; further responsibilities to be agreed |
| Julián Valencia | Developer, analyst, and data engineer: relational dataset analysis, data extraction, schema requirements |

Human review tasks (clause wording, Portuguese copy, labels, thresholds) are listed with their status under "Pending human actions" in `docs/PROGRESS.md`.

## 11. Skills

Skills are plain Markdown instructions any agent can read before a task. Read the matching one first.

For GitHub pull requests, issues, reviews, comments, or other GitHub operations, read [skills/github-collaboration/SKILL.md](skills/github-collaboration/SKILL.md) before acting. Use the repository's `origin` remote to identify the target repository.

| Skill | Use it for |
|---|---|
| [github-collaboration](skills/github-collaboration/SKILL.md) | Pull requests, issues, reviews, and comments through the `gh` CLI, with authentication checks and no stored tokens |
| [download-organizer-data](skills/download-organizer-data/SKILL.md) | Downloading the organizer S3 dataset with credentials the contributor supplies for that run only, never stored or echoed |
| [setup-postgres-data](skills/setup-postgres-data/SKILL.md) | Setting up the local PostgreSQL, applying migrations, and seeding from an existing warehouse or the committed sample |

The design skills under `.claude/skills/` (`design-taste-frontend`, `minimalist-ui`, `full-output-enforcement`) are written for Claude Code, but CLAUDE.md section 6 asks all UI work to follow the first two; other agents can read their `SKILL.md` files directly.

## 12. Keeping this file current

- Update this file in the same pull request when a rule, a convention, a `make` target, a top-level directory, a recipe step, or a settled decision changes.
- Keep status out of it. `docs/PROGRESS.md` is the source of truth for the current phase and the pending human actions; section 3 here is a short pointer, refreshed when a phase closes.
- Link to package READMEs, ADRs, and docs instead of copying them.
- There is no `AGENT.md`; this file is the single agent guide. Do not create a second one.
- CLAUDE.md changes only with the human's approval.
- After editing, run `make docs-check` and the emoji guard (`uv run --no-project --python 3.12 python scripts/checks/check_no_emoji.py`).
