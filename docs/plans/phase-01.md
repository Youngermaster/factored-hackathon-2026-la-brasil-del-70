# Phase 01 plan: monorepo scaffold and quality gates

Status: approved on 2026-09-26 with the decisions below. Written against commit `dbb23d3`.

## Approved decisions

The human approved this plan with these answers to the open questions. Where a decision changes the plan text below (package manager), the decision wins.

1. **License:** none yet. No LICENSE file is added. "License undecided, decide before submission" is recorded in `docs/PROGRESS.md` and `docs/BACKLOG.md`, owned by phase 17.
2. **Large dev dependencies:** mermaid (with jsdom) and mypy are approved despite the 50 MB rule. The approval is recorded in the phase log.
3. **Node:** Node v24.21.0 is installed through nvm and is the nvm default. jsdom 30.x, `engines` `>=24.15.0 <25`, `.nvmrc` `24`.
4. **Package manager: pnpm instead of npm everywhere.** `apps/web` uses pnpm (10.33.0) with a committed `pnpm-lock.yaml` and a `packageManager` field. The Makefile, the pre-commit web hooks, CI (`pnpm/action-setup` pinned by SHA, `pnpm install --frozen-lockfile`, `pnpm audit --prod --audit-level high`), and the docs use pnpm. CLAUDE.md text that names npm is updated to the pnpm equivalents, and CLAUDE.md section 3 gains one line stating that later phase prompts that say npm or npx mean pnpm or `pnpm dlx`. The human explicitly authorized this CLAUDE.md edit. Every `npm` command in the sections below reads as its pnpm equivalent (`npm ci` becomes `pnpm install --frozen-lockfile`, `npm --prefix apps/web run X` becomes `pnpm --dir apps/web run X`, `package-lock.json` becomes `pnpm-lock.yaml`).
5. **Other recommendations accepted:** testcontainers for PostgreSQL in CI and locally (no service container); `bank_owner` as the development and test owner, with production hardening deferred to phase 16; the extra 80% coverage gates on `bootstrap`, `bank_data`, `bank_ml`, and `bank_evals`; markdownlint MD032 and MD060 disabled; guard scripts run through `uv run --no-project --python 3.12 python`.

This phase creates the skeleton from CLAUDE.md section 4 with every quality gate running from the first commit: lint, format, types, import boundaries, tests with coverage gates, security scans, and docs checks. It also closes the five phase 00 backlog items that phase 01 owns. Domain models, business logic, and design work stay out of scope.

## Read-only findings

The checks below were run before writing this plan. Scratch experiments ran in the session scratchpad, never in the repository.

### Toolchain and registry state

| Item | Finding | Consequence |
|---|---|---|
| Python | 3.12.13 through uv 0.11.17 (latest uv is 0.12.19) | Pin `requires-python = ">=3.12,<3.13"`, add `.python-version` (`3.12`), and `[tool.uv] required-version = ">=0.11.17"`. CI pins uv 0.11.17 so the lockfile format matches the local tool |
| Node | v24.14.1 locally; latest 24.x is 24.21.0 | jsdom 30.1.1 (a Vitest environment and the Mermaid check need it) declares `node: ^24.15.0`; `npm install` prints EBADENGINE warnings on 24.14.1. See open question 4 |
| TypeScript | latest is 7.0.2 (the native port) | typescript-eslint 8.70.1 peers on `typescript <6.1.0`, so this plan pins TypeScript 6.0.3 |
| ESLint | latest is 10.11.0 | eslint-plugin-jsx-a11y 6.10.2 peers on ESLint `^9` at most, so this plan pins ESLint 9.39.5 and `@eslint/js` 9.39.5 (the maintained 9.x line) |
| mypy | 2.3.1; installed size about 63 MB (17 MB package, 38 MB compiled extension, 8 MB mypyc) | Over the 50 MB threshold; see open question 3 |
| mermaid | 12.0.0; 123 MB unpacked on its own, 239 MB `node_modules` together with jsdom and markdownlint-cli2 | Over the 50 MB threshold; see open question 2 |
| Docker images | postgres `16.15-alpine3.24`, `otel/opentelemetry-collector:0.161.0` (core, about 35 MB per architecture), `jaegertracing/jaeger:2.21.0`, `prom/prometheus:v3.15.0`, `grafana/grafana:13.2.2`, `ghcr.io/mlflow/mlflow:v3.16.1`, `node:24.21.0-alpine3.24`, `ghcr.io/astral-sh/uv:0.11.17-python3.12-trixie-slim` (the bookworm variant does not exist for 0.11.17) | Every image is pinned to these tags. Grafana and MLflow are large pulls, but only when their profiles run |
| GitHub Actions | `actions/checkout` v7.0.1 (`3d3c42e5aac5ba805825da76410c181273ba90b1`), `actions/setup-node` v7.0.0 (`820762786026740c76f36085b0efc47a31fe5020`), `astral-sh/setup-uv` v10.2.0 (`c18668ad3cf93ea998bef934396af7bb5c839dc7`) | Pinned by commit SHA with the tag in a trailing comment |
| pre-commit hook repos | gitleaks v8.30.1, pre-commit-hooks v6.0.0, ruff-pre-commit v0.16.9 | `pre-commit autoupdate` moves the seed pins to these releases |

### Scratch experiments

| Experiment | Result | Consequence |
|---|---|---|
| `mermaid.parse` in plain Node | flowchart, state, and class diagrams fail with `DOMPurify.addHook is not a function`; only sequence diagrams parse | The check script installs a jsdom `window` and `document` on `globalThis` before importing mermaid |
| `mermaid.parse` with a jsdom window | flowchart, sequence, stateDiagram-v2, and classDiagram parse; three malformed inputs fail with line-numbered errors | The approach from the prompt works without a headless browser |
| import-linter 2.15 with a `layers` contract and a `forbidden` contract listing packages that are not installed (`litellm`, `boto3`) | Both contracts report violations correctly; absent external packages cause no error | The forbidden contract can list all five packages from day one |
| mypy 2.3.1 per-module `strict = true` override | Works (flags an untyped function in the overridden module only) | Either global or per-module strictness is available; this plan uses global strict (see tool configuration) |
| uv virtual workspace root (no `[project]` table) with `[dependency-groups]` | `uv lock` and `uv sync --all-packages` install the group and every member's console scripts | The root `pyproject.toml` stays a virtual root |
| Compose v5.5.1 with a `${VAR:?}` variable used only by a service in an inactive profile | Interpolation fails even when that profile is not enabled | Only the PostgreSQL passwords may be required variables. Grafana uses local anonymous viewer access instead of an admin password |
| markdownlint-cli2 0.23.3 over the seven committed Markdown files, with MD013 (line length), MD033, and MD041 off | 216 findings: 180 MD060 (compact `\|---\|` table style) and 36 MD032 (list directly under a bold lead-in line, mostly in CLAUDE.md). With MD032 and MD060 also off: 0 findings | See open question 8 |

## Directory tree

New files are marked `+`, changed files `~`. Directories that later phases own (`contracts/`, `policies/`, `docs/adr` content beyond 0003, `tests/contracts/`) are not created empty.

```text
.
├── ~ .gitignore                         + coverage.json, apps/web/.vite/
├── ~ .pre-commit-config.yaml            ruff, format, yaml/json/toml checks, web hooks, autoupdated pins
├── ~ .env.example                       no new variables expected (see compose design)
├── + .python-version                    3.12
├── + .nvmrc                             24
├── + .markdownlint-cli2.jsonc           repository markdownlint config
├── + Makefile
├── + pyproject.toml                     uv workspace root and shared tool configuration
├── + uv.lock
├── + conftest.py                        marks tests unit or integration by directory, blocks the network for unit tests
├── + docker-compose.yml
├── + SECURITY.md
├── + CONTRIBUTING.md
├── ~ README.md                          first full version
├── + .github/
│   ├── workflows/ci.yml
│   └── pull_request_template.md
├── + apps/web/
│   ├── package.json, package-lock.json
│   ├── index.html, vite.config.ts, tsconfig.json, tsconfig.app.json, tsconfig.node.json
│   ├── eslint.config.js, .prettierrc.json, .prettierignore
│   ├── Dockerfile.dev                   dev server image for the compose web profile (non-root)
│   ├── README.md
│   └── src/
│       ├── main.tsx, index.css, vite-env.d.ts
│       ├── app/        README.md, App.tsx, App.test.tsx
│       ├── shared/     README.md
│       ├── entities/   README.md
│       ├── features/   README.md
│       ├── pages/      README.md
│       └── test/       setup.ts, msw/server.ts, msw/handlers.ts, msw.test.ts, boundaries.test.ts
├── + services/api/
│   ├── pyproject.toml                   distribution bank-agent, console script bank-agent
│   ├── Dockerfile.dev                   hot-reload image for the compose api profile (non-root)
│   ├── README.md
│   ├── src/bank_agent/
│   │   ├── __init__.py
│   │   ├── asgi.py                      ASGI entry point: settings -> logging -> container -> create_app
│   │   ├── cli.py                       typer app: version
│   │   ├── domain/      __init__.py, README.md
│   │   ├── ports/       __init__.py, README.md, health.py (ReadinessCheck Protocol)
│   │   ├── policy/      __init__.py, README.md
│   │   ├── application/ __init__.py, README.md
│   │   ├── adapters/    __init__.py, README.md, persistence/postgres/readiness.py
│   │   ├── api/         __init__.py, README.md, app.py, provider.py, middleware.py, problems.py, routers/health.py
│   │   ├── bootstrap/   __init__.py, README.md, settings.py, logging.py, container.py
│   │   └── prompts/     __init__.py, README.md
│   └── tests/
│       ├── unit/        bootstrap/, api/, test_cli.py, test_network_guard.py, test_import_contracts.py
│       └── integration/ conftest.py, test_health_ready.py, test_database_roles.py
├── + data_platform/  pyproject.toml (bank-data), README.md, src/bank_data/{__init__,cli}.py, tests/unit/test_cli.py
├── + ml/             pyproject.toml (bank-ml),   README.md, src/bank_ml/{__init__,cli}.py,   tests/unit/test_cli.py
├── + evals/          pyproject.toml (bank-evals), README.md, src/bank_evals/{__init__,cli}.py, tests/unit/test_cli.py
├── + deploy/
│   ├── README.md
│   ├── postgres/init/10-roles.sh        owner and application role setup
│   └── observability/
│       ├── otel-collector.yaml
│       ├── prometheus.yml
│       └── grafana/provisioning/datasources/datasources.yaml
├── scripts/
│   ├── checks/
│   │   ├── + check_coverage_gates.py    per-layer coverage gates from pyproject
│   │   ├── + check_mermaid.mjs          parses every fenced mermaid block with the mermaid package
│   │   └── + tests/check_mermaid.test.mjs  node:test self-test with temporary valid and invalid files
│   ├── hooks/+ run_web_tool.sh          runs eslint or prettier inside apps/web on staged paths
│   └── + tests/unit/                    test_check_env_keys.py, test_check_coverage_gates.py, test_check_no_emoji.py
└── docs/
    ├── + README.md                      documentation index
    ├── + architecture/overview.md       Mermaid flowchart of components and dependency direction
    ├── + adr/README.md, 0001-record-architecture-decisions.md,
    │     0002-uv-workspace-and-hexagonal-backend.md, 0003-frontend-layering-and-state.md
    ├── ~ PROGRESS.md, ~ BACKLOG.md
    └── plans/phase-01.md                this file
```

Package names follow the prompts: `bank_agent`, `bank_data` (the data platform; later phases add `data_platform/dbt`, `fixtures`, `mappings`, `seed`, and `analysis` beside `src/`), `bank_ml`, and `bank_evals`. Build backend: `uv_build`, which maps `bank-agent` to `src/bank_agent` without extra configuration.

## Backend design decisions

### Entry points and the `api | bootstrap` layer

The prompt's layers contract makes `api` and `bootstrap` independent siblings (`|`), so neither may import the other. The wiring therefore lives in two package-root modules that are not part of any layer: `bank_agent/asgi.py` (the uvicorn factory target) and `bank_agent/cli.py` (the `bank-agent` typer app). A third import-linter contract forbids every layer from importing them.

- `api/provider.py` defines a `ServiceProvider` Protocol: what the HTTP layer needs (readiness checks, API config, `aclose()`).
- `bootstrap/container.py` builds the concrete `Container`, which satisfies `ServiceProvider` structurally. It is the only module that constructs adapters.
- `api/app.py`: `create_app(provider: ServiceProvider) -> FastAPI`. It stores the provider on `app.state`, and its lifespan closes it.
- `asgi.py`: `create_app()` factory that loads settings, configures logging, builds the container, and calls `api.app.create_app`.

This keeps CLAUDE.md section 5 ("FastAPI dependencies resolve from the container") true through dependency inversion. ADR 0002 records it.

### Settings (`bootstrap/settings.py`)

pydantic-settings classes whose environment names match `.env.example` exactly:

| Class | Env prefix | Fields |
|---|---|---|
| `RuntimeSettings` | none | `app_env` (`development`, `test`, `production`), `demo_mode`, `log_level` |
| `DatabaseSettings` | `POSTGRES_` | `host`, `port`, `db`, `admin_user`, `admin_password`, `app_user`, `app_password` (passwords are `SecretStr \| None`); `is_configured` is true when the app password is set |
| `SecuritySettings` | none | `session_secret`, `csrf_secret` (`SecretStr`), `cors_allowed_origins` (comma-separated list) |
| `LLMSettings` | `LLM_` | `provider` (`fake`, `cassette`, `litellm`), models, keys (`SecretStr \| None`), `daily_budget_usd` (`Decimal`), `session_token_limit` |
| `ObservabilitySettings` | `OTEL_` | `exporter_otlp_endpoint`, `service_name` |

`AppSettings` aggregates them, and `load_settings()` applies the production rules when `APP_ENV=production`: `DEMO_MODE` must be false; session, CSRF, and both database secrets must be non-empty, at least 32 characters, and not in a denylist of known defaults (`changeme`, `secret`, `password`, `dev`, `test`, and similar); LLM keys are required when the provider is `litellm`. Errors name the offending field and never its value. Only `bootstrap/` reads the environment. Tests pass `_env_file=None` and an explicit environment, so a developer's `.env` can never influence them. Model-registry and S3 settings arrive with phases 10 and 03, which own them.

### Logging and redaction (`bootstrap/logging.py`)

`configure_logging(settings)` sets structlog to JSON output with ISO UTC timestamps, log level, contextvars (request id), exception formatting, and a `RedactionProcessor` placed after exception formatting and before rendering, so traceback text is scrubbed too.

- Key masking, case-insensitive, recursive through dicts, lists, and tuples: `document_number`, `email`, `mobile_phone`, `landline_phone`, `address`, `password`, `otp`, `token`, `secret`, `authorization`, `cookie`, plus any key containing `password`, `secret`, `token`, `api_key`, `authorization`, or `cookie` (for example `access_token`, `set-cookie`).
- Value scrubbing on every string: email addresses; Brazilian CPF (`123.456.789-09`); Mexican CURP (`GODE561231HDFRRN09`); Argentine DNI (`30.123.456`); Colombian CC with dot grouping (`1.020.304.050`); phone numbers with separators; and any run of 7 or more digits.
- Masked values become `[REDACTED]`, or `[REDACTED:email]` style labels for scrubbed patterns, so logs stay debuggable without the data.

### HTTP surface (`api/`)

- `GET /health/live`: always `200 {"status": "live"}`.
- `GET /health/ready`: runs each `ReadinessCheck` with a 2 second timeout. All pass: `200 {"status": "ready", "checks": {"database": "ok"}}`. Any failure: `503 {"status": "not_ready", "checks": {"database": "unavailable"}}`, without exception text. With no database configured there is no database check; production cannot reach that state because settings refuse empty database secrets there.
- `RequestIdMiddleware` (pure ASGI): accepts an inbound `X-Request-ID` matching `^[A-Za-z0-9-]{8,64}$`, otherwise generates one with an injected id factory (the `IdGenerator` port arrives in phase 02); binds it to structlog contextvars; echoes it in the response.
- `problems.py`: RFC 9457 `application/problem+json` handlers for HTTP errors, validation errors (location and error type only, never the rejected input), and a catch-all 500 that logs the exception and returns a generic body. A registry maps exception types to status, type URI, and title, so phase 02 registers domain errors in one place.
- `adapters/persistence/postgres/readiness.py`: `SELECT 1` through a SQLAlchemy `AsyncEngine` (asyncpg), connecting as the application role. The container creates the engine with `pool_pre_ping` and disposes it on shutdown.

### CLIs

`bank-agent`, `bank-data`, `bank-ml`, and `bank-eval` are typer apps with `no_args_is_help=True`, a root callback (so subcommands stay subcommands), and a `version` command that prints the distribution name and version from `importlib.metadata`. Phase 07 adds `bank-agent index build`.

### The `ml` extra

CLAUDE.md places sentence-transformers in an optional `ml` extra of the API package. No heavy ML dependency is declared in this phase: phase 07 adds the extra with the dense retriever, and phase 10 adds scikit-learn, LightGBM, and MLflow to `bank_ml` when training code exists. Declaring them now would put torch into the lockfile with no code using it. The rule is documented in `services/api/README.md` and ADR 0002.

## Tool configuration

All Python tool configuration lives in the root `pyproject.toml`.

### ruff

- `target-version = "py312"`, `line-length = 120` (the existing guard scripts already use it), `src` set to every package's `src` and `tests` plus `scripts`.
- Lint rules: `E`, `W`, `F` (pycodestyle and pyflakes), `I` (isort, first-party packages declared), `UP` (pyupgrade), `B` (bugbear), `S` (bandit rules), `C4`, `SIM`, `RUF`, `PT` (pytest style), `N` (naming), `ASYNC`, `DTZ` (timezone-aware datetimes), `T20` (no stray `print`), `PTH` (pathlib), `ERA` (commented-out code), `TID` (banned relative imports beyond siblings), `PL` subset `PLE` and `PLW`.
- Per-file ignores: tests allow `S101` (assert) and `PLR2004`; `scripts/` allows `T201` because the guard scripts print by design.
- `ruff format` with default double quotes.

### mypy

Global `strict = true` for all first-party code, which includes the four layers CLAUDE.md requires (`domain`, `ports`, `policy`, `application`) and goes further. `plugins = ["pydantic.mypy"]`, `warn_unreachable = true`, `python_version = "3.12"`. Any future relaxation must be a per-module override for a third-party import (`ignore_missing_imports`), never for the four strict layers; a comment in `pyproject.toml` and ADR 0002 state this. mypy runs once per package (`src` and `tests` together), because several packages have a `tests` directory and a `conftest.py`, which would collide as module names in a single run.

### import-linter

```toml
[tool.importlinter]
root_packages = ["bank_agent"]
include_external_packages = true

[[tool.importlinter.contracts]]
name = "Hexagonal layers, inward dependencies only"
type = "layers"
layers = [
  "bank_agent.api | bank_agent.bootstrap",
  "bank_agent.adapters",
  "bank_agent.application",
  "bank_agent.policy",
  "bank_agent.ports",
  "bank_agent.domain",
]

[[tool.importlinter.contracts]]
name = "Pure core has no framework or I/O imports"
type = "forbidden"
source_modules = ["bank_agent.domain", "bank_agent.ports", "bank_agent.policy"]
forbidden_modules = ["fastapi", "sqlalchemy", "httpx", "boto3", "litellm"]

[[tool.importlinter.contracts]]
name = "Layers never import the entry points"
type = "forbidden"
source_modules = ["bank_agent.domain", "bank_agent.ports", "bank_agent.policy",
                  "bank_agent.application", "bank_agent.adapters", "bank_agent.api", "bank_agent.bootstrap"]
forbidden_modules = ["bank_agent.asgi", "bank_agent.cli"]
```

`test_import_contracts.py` is a negative control: it copies the contracts from `pyproject.toml` into a temporary config, builds a temporary package tree with one violation per contract, runs `lint-imports` as a subprocess, and asserts each contract reports broken. Without it, a misconfigured contract could pass silently.

### pytest

```toml
[tool.pytest.ini_options]
minversion = "9.0"
testpaths = ["services/api/tests", "data_platform/tests", "ml/tests", "evals/tests", "scripts/tests"]
addopts = ["-ra", "--strict-markers", "--strict-config", "--import-mode=importlib", "--allow-unix-socket"]
markers = [
  "unit: fast tests with no network, database, or filesystem outside tmp_path",
  "integration: tests against real PostgreSQL, DuckDB files, or the ASGI app with real adapters",
]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
xfail_strict = true
filterwarnings = ["error"]
```

- The root `conftest.py` marks each collected test `unit` or `integration` from its directory (`tests/unit/`, `tests/integration/`), and fails collection for a test in neither, so no test escapes classification. Tests under a future `tests/contracts/` must carry an explicit marker per parameter.
- Unit tests also receive pytest-socket's `disable_socket` marker. With `--allow-unix-socket`, the asyncio event loop's internal socket pair still works, but any TCP or UDP socket raises `SocketBlockedError`. `test_network_guard.py` proves it.
- `filterwarnings = ["error"]` turns new deprecation warnings into failures. Any third-party warning that must be tolerated gets a targeted ignore with a reason comment.

### Coverage gates

coverage.py has no per-directory thresholds, so the gates live in a table and a small checker enforces them:

```toml
[tool.coverage.run]
source = ["bank_agent", "bank_data", "bank_ml", "bank_evals"]
branch = true
relative_files = true

[tool.bank.coverage-gates]   # minimum line coverage, percent
"services/api/src/bank_agent/domain" = 90
"services/api/src/bank_agent/ports" = 90
"services/api/src/bank_agent/policy" = 90
"services/api/src/bank_agent/application" = 90
"services/api/src/bank_agent/adapters" = 80
"services/api/src/bank_agent/api" = 80
"services/api/src/bank_agent/bootstrap" = 80   # proposed, open question 7
"data_platform/src" = 80                        # proposed, open question 7
"ml/src" = 80                                   # proposed, open question 7
"evals/src" = 80                                # proposed, open question 7
```

Unit tests write `.coverage.unit`, integration tests write `.coverage.integration`, and `coverage combine` merges them, because API and adapter coverage comes mostly from integration tests. `scripts/checks/check_coverage_gates.py` reads the combined `coverage.json`, sums covered and total statements per prefix, prints one line per gate, and exits 1 on any miss. A prefix with zero statements prints `no statements yet` and passes explicitly, so empty layers never pass by accident without saying so.

### Web: TypeScript, ESLint, Prettier, Vitest, MSW

- `tsconfig.app.json`: `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride`, `noFallthroughCasesInSwitch`, `verbatimModuleSyntax`, `moduleResolution: "bundler"`, `jsx: "react-jsx"`, path alias `@/*` to `src/*`, `noEmit`. No comments in any tsconfig, so `check-json` validates them unchanged.
- ESLint 9 flat config (`eslint.config.js`): `@eslint/js` recommended, `typescript-eslint` `strictTypeChecked` and `stylisticTypeChecked` with `projectService`, `eslint-plugin-react-hooks` recommended, `eslint-plugin-react-refresh`, `eslint-plugin-jsx-a11y` strict, `eslint-config-prettier` last. Extra rules: `@typescript-eslint/no-explicit-any` error, `react/no-danger` equivalent through `no-restricted-syntax` banning `dangerouslySetInnerHTML`, `no-restricted-globals` for `localStorage` and `sessionStorage`.
- Boundaries (`eslint-plugin-boundaries` 7.2.0 with its `boundaries/dependencies` policy rule and `eslint-import-resolver-typescript`): element types `app`, `pages`, `features` (captured per feature folder), `entities`, `shared`, and `test`. Policies, default `disallow`: `app` may import everything below it; `pages` may import `features`, `entities`, `shared`; `features` may import `entities`, `shared`, and other features only through their `index.ts`; `entities` may import `shared`; `shared` imports only `shared`; imports within the same feature are allowed. `boundaries.test.ts` lints violating snippets through the ESLint Node API (for example an entity importing a feature, a page importing a feature internal) and asserts the rule fires, plus one allowed import that must pass.
- Prettier 3.9.9 with `printWidth: 100` and `singleQuote: true`; `.prettierignore` covers `dist`, `coverage`, and `src/shared/api/generated`.
- Vitest 5.0.2 configured in `vite.config.ts`: `environment: "jsdom"`, `setupFiles: ["src/test/setup.ts"]`, coverage with the v8 provider over `src/**/*.{ts,tsx}` (excluding tests, `main.tsx`, and generated code) and a per-glob threshold of 70% lines for `src/features/**`.
- `src/test/setup.ts` registers jest-dom matchers and the MSW node server with `onUnhandledRequest: "error"`, resetting handlers after each test. `msw/handlers.ts` holds a sample `GET /health/live` handler.
- Minimal shell: `App.tsx` renders a `main` landmark with the product name as its only text. The product name is a proper noun, not translated copy, so no locale files are needed yet; phase 12 adds i18next and the real shell.

### Markdown and Mermaid (`make docs-check`)

- `.markdownlint-cli2.jsonc` at the root: `globs: ["**/*.md"]`, `gitignore: true`, ignores `kit/**`, `**/node_modules/**`, and `.claude/skills/**`. Config: defaults on; MD013 (line length) and MD033 (inline HTML) off; MD041 off (ADR and template files); MD024 `siblings_only`; MD032 and MD060 per open question 8.
- `scripts/checks/check_mermaid.mjs`: lists Markdown files with `git ls-files --cached --others --exclude-standard` minus the same exclusions, extracts fenced `mermaid` blocks with their line numbers, installs a jsdom window, resolves `mermaid` and `jsdom` from `apps/web` with `createRequire`, parses each block, prints `path:line: message` for failures, and exits 1 on any. `node --test scripts/checks/tests/` writes a valid and an invalid diagram to a temporary directory and asserts pass and fail.

## docker-compose design

`docker-compose.yml` at the root, project name `bank-agent`. Every published port binds to `127.0.0.1`. Only the two PostgreSQL passwords are required variables (`${VAR:?set VAR in .env, see .env.example}`), because Compose interpolates required variables even for inactive profiles.

| Service | Profile | Image | Notes |
|---|---|---|---|
| `postgres` | always on | `postgres:16.15-alpine3.24` | `POSTGRES_USER` from `POSTGRES_ADMIN_USER` (`bank_owner`), database `bank_agent`, named volume `pgdata`, `./deploy/postgres/init` mounted read-only at `/docker-entrypoint-initdb.d`. Healthcheck `pg_isready -h 127.0.0.1` so it stays unhealthy while the init scripts run on the socket-only temporary server |
| `api` | `api` | built from `services/api/Dockerfile.dev` on `ghcr.io/astral-sh/uv:0.11.17-python3.12-trixie-slim` | Non-root user created in the image with `/opt/venv` owned by it; repository bind-mounted read-only; named volumes for the virtual environment and uv cache; `uv run --frozen --package bank-agent uvicorn bank_agent.asgi:create_app --factory --reload`; `env_file: .env` (required); `POSTGRES_HOST=postgres`; `depends_on` postgres healthy; healthcheck on `/health/live`; `no-new-privileges`, `cap_drop: [ALL]` |
| `web` | `web` | built from `apps/web/Dockerfile.dev` on `node:24.21.0-alpine3.24` | Runs as the image's `node` user; `apps/web` bind-mounted; `node_modules` in a named volume so Linux-native binaries never mix with the host's; `npm ci && npm run dev -- --host 0.0.0.0`; `VITE_API_PROXY_TARGET=http://api:8000` for the Vite proxy of `/health` and `/api` |
| `otel-collector` | `obs` | `otel/opentelemetry-collector:0.161.0` | Core distribution (it includes the OTLP receiver, OTLP exporter, and Prometheus exporter). Receives OTLP on 4317 and 4318, batches with a memory limiter, exports traces to Jaeger over OTLP and metrics on a Prometheus endpoint (8889) |
| `jaeger` | `obs` | `jaegertracing/jaeger:2.21.0` | Jaeger v2 all-in-one with in-memory storage; UI on 16686 |
| `prometheus` | `obs` | `prom/prometheus:v3.15.0` | Scrapes the collector and itself; `--storage.tsdb.retention.time=7d` |
| `grafana` | `obs` | `grafana/grafana:13.2.2` | Provisioned Prometheus and Jaeger datasources. Local-only anonymous `Viewer` access with the login form and basic auth disabled, so no admin password is needed; dashboards are file-provisioned in phase 15, which also adds alert rules |
| `mlflow` | `ml` | `ghcr.io/mlflow/mlflow:v3.16.1` | `mlflow server` with a SQLite backend store and a local artifact root on a named volume; port 5000 |

`deploy/postgres/init/10-roles.sh` (POSIX sh, `set -eu`, `psql -v ON_ERROR_STOP=1`, values passed as psql variables, never echoed):

1. Owner role: the image creates `POSTGRES_USER` (`bank_owner`) as the bootstrap role; the script creates schema `app` owned by it, revokes `CREATE` on `public` from `PUBLIC`, and sets the database search path. See open question 6 for the alternative with a separate non-superuser owner.
2. Application role `bank_app`: `LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS`, password from `POSTGRES_APP_PASSWORD`; `CONNECT` on the database and `USAGE` on schema `app`; default privileges from the owner granting `SELECT, INSERT, UPDATE, DELETE` on future tables and `USAGE` on future sequences. It owns nothing. Phase 05 revokes `UPDATE` and `DELETE` on the append-only tables it creates.

`make up` runs `docker compose up -d --wait` (PostgreSQL only); `make up PROFILES="api web obs"` adds profiles. `make down` runs `docker compose --profile '*' down`.

## Makefile

`SHELL := bash` with `-eu -o pipefail`, `.DEFAULT_GOAL := help`. Python runs through `uv run --frozen`; the stdlib guard scripts run through `uv run --no-project --python 3.12 python` (see the backlog items below).

| Target | Recipe |
|---|---|
| `help` | Lists every target with a `##` description |
| `setup` | `uv sync --all-packages --frozen`, `npm --prefix apps/web ci`, `pre-commit install --install-hooks` |
| `up`, `down` | As in the compose design |
| `lint` | `ruff check`, `ruff format --check`, `lint-imports`, `bandit -c pyproject.toml -r` over every `src` and `scripts`, web `eslint . --max-warnings=0` and `prettier --check .` |
| `format` | `ruff format`, `ruff check --fix`, web `prettier --write .` and `eslint --fix` |
| `typecheck` | mypy once per package, web `tsc -b` |
| `test-unit` | `pytest -m unit` with coverage into `.coverage.unit` |
| `test-integration` | `pytest -m integration` with coverage into `.coverage.integration` (needs Docker for testcontainers) |
| `test-web` | `npm --prefix apps/web run test:coverage` |
| `env-check` | `scripts/checks/check_env_keys.py`; not part of `check`, because `check` must pass without `.env` |
| `docs-check` | `markdownlint-cli2` with the root config, `node scripts/checks/check_mermaid.mjs`, `node --test scripts/checks/tests/` |
| `check` | `lint`, `typecheck`, `test-unit`, `test-integration`, then `coverage combine` and `check_coverage_gates.py`, `test-web`, `docs-check`, then the emoji check, the attribution check over `HEAD`, and `gitleaks git --redact --no-banner .` |

No other public targets. `make security` and the rest arrive with the phases that implement them.

## pre-commit

Keep every seed hook, run `pre-commit autoupdate` (gitleaks v8.30.1, pre-commit-hooks v6.0.0), and add:

- `astral-sh/ruff-pre-commit` v0.16.9: `ruff-check --fix` and `ruff-format`. The rev matches the ruff pin in `uv.lock`.
- pre-commit-hooks: `check-yaml`, `check-json`, `check-toml`.
- Local `web-eslint` and `web-prettier` hooks (`language: system`, `files: ^apps/web/`) through `scripts/hooks/run_web_tool.sh`, which strips the `apps/web/` prefix and runs the tool from `apps/web`, so the flat config and tsconfig resolve correctly.
- The `strip-ai-attribution` and `no-emoji` entries change from `python3` to `uv run --no-project --python 3.12 python`, which closes the interpreter backlog item (open question 9).

## CI design (`.github/workflows/ci.yml`)

Triggers: `push` to `main`, `pull_request`, `workflow_dispatch`, and a weekly `schedule` for the audit. Top-level `permissions: contents: read`. `concurrency: ci-${{ github.workflow }}-${{ github.ref }}` with `cancel-in-progress` for pull requests. Every job runs on `ubuntu-24.04` with `timeout-minutes`, checks out with `persist-credentials: false`, and uses SHA-pinned actions. No job reads repository secrets.

| Job | Steps |
|---|---|
| `python` | setup-uv (uv 0.11.17, cache keyed on `uv.lock`); `uv sync --all-packages --frozen`; ruff check; ruff format check; mypy per package; `lint-imports`; bandit; unit tests; integration tests against PostgreSQL (open question 5); coverage combine and gate |
| `web` | setup-node from `.nvmrc` with npm cache on `apps/web/package-lock.json`; `npm ci`; lint (ESLint and Prettier check); typecheck; `vitest run --coverage`; `vite build` |
| `guards` | checkout with `fetch-depth: 0`; download gitleaks 8.30.1 and verify it against a SHA-256 literal pinned in the workflow; `gitleaks git --redact --no-banner .` over the full history; emoji check; attribution check over the full history; setup-node and `npm ci`; `make docs-check`; `docker compose config --quiet` with throwaway values generated in the step |
| `audit` | `uv export --frozen --all-packages --no-emit-workspace` then `pip-audit -r` with `--require-hashes`; `npm audit --omit=dev --audit-level=high` in `apps/web` |

pip-audit has no severity filter, so it fails on any known vulnerability, which is stricter than the high-severity rule in CLAUDE.md section 7. Any accepted finding gets an explicit `--ignore-vuln` with a reason in the workflow.

## Dependencies to add

Runtime dependencies use `>=current,<next major` in `pyproject.toml` and `package.json` ranges; exact versions are pinned by `uv.lock` and `package-lock.json`. Dev tools that also run in pre-commit or CI are pinned exactly to avoid drift. All licenses are permissive; hypothesis (MPL-2.0) is dev-only.

### Python runtime (`bank-agent`)

| Package | Version | License | Why |
|---|---|---|---|
| fastapi | 0.141.1 | MIT | API framework (stack) |
| pydantic | 2.13.5 | MIT | Models and validation (stack) |
| pydantic-settings | 2.15.0 | MIT | Environment-only configuration (rule 4) |
| uvicorn[standard] | 0.54.0 | BSD-3-Clause | ASGI server; the extra brings watchfiles for `--reload` |
| structlog | 26.1.0 | MIT or Apache-2.0 | JSON logging with redaction (stack) |
| typer | 0.27.2 | MIT | CLIs (stack); also the only runtime dependency of `bank-data`, `bank-ml`, and `bank-evals` |
| sqlalchemy[asyncio] | 2.1.1 | MIT | Async engine for the readiness check; phase 05 builds persistence on it |
| asyncpg | 0.31.0 | Apache-2.0 | PostgreSQL driver for the async engine |

### Python dev group (root `[dependency-groups] dev`)

| Package | Version | License | Why |
|---|---|---|---|
| pytest | 9.1.1 | MIT | Test runner |
| pytest-asyncio | 1.4.0 | Apache-2.0 | Async tests, `asyncio_mode = "auto"` |
| pytest-socket | 0.8.1 | MIT | Blocks the network in unit tests |
| pytest-cov | 7.1.0 | MIT | Coverage collection (brings coverage 7.16.1) |
| hypothesis | 6.168.1 | MPL-2.0 | Property test for the redaction processor |
| testcontainers | 4.15.0 | Apache-2.0 | Throwaway PostgreSQL for integration tests |
| httpx | 0.28.1 | BSD-3-Clause | ASGI transport for API tests (dev only for now; forbidden in the pure core) |
| ruff | 0.16.9 | MIT | Lint and format |
| mypy | 2.3.1 | MIT | Type checking; about 63 MB installed, open question 3 |
| import-linter | 2.15 | BSD-2-Clause | Layer contracts |
| bandit | 1.9.4 | Apache-2.0 | Security lint |
| pip-audit | 2.10.1 | Apache-2.0 | Dependency vulnerability audit |

### Web (`apps/web`)

| Package | Version | Kind | Why |
|---|---|---|---|
| react, react-dom | 19.3.0 | dependency | UI runtime (stack) |
| vite | 8.3.1 | dev | Build and dev server |
| @vitejs/plugin-react | 6.1.1 | dev | React support for Vite 8 |
| typescript | 6.0.3 | dev | Not 7.x: typescript-eslint requires `<6.1.0` |
| @types/react, @types/react-dom | 19.3.0 | dev | Types |
| @types/node | 24.19.0 | dev | Node 24 types for config files and scripts |
| tailwindcss, @tailwindcss/vite | 4.3.3 | dev | Tailwind v4 through the Vite plugin |
| eslint, @eslint/js | 9.39.5 | dev | Not 10.x: jsx-a11y peers on ESLint 9 at most |
| typescript-eslint | 8.70.1 | dev | Strict type-aware rules |
| eslint-plugin-react-hooks | 7.1.1 | dev | Hooks rules |
| eslint-plugin-react-refresh | 0.5.7 | dev | Fast-refresh safety |
| eslint-plugin-jsx-a11y | 6.10.2 | dev | Accessibility lint (last release 2024-10; still the standard choice) |
| eslint-plugin-boundaries | 7.2.0 | dev | Layer boundaries |
| eslint-import-resolver-typescript | 4.4.5 | dev | Lets boundaries resolve TypeScript paths |
| eslint-config-prettier | 10.1.8 | dev | Turns off rules Prettier owns |
| globals | 17.12.0 | dev | Browser and Node globals for the flat config |
| prettier | 3.9.9 | dev | Formatting |
| vitest, @vitest/coverage-v8 | 5.0.2 | dev | Tests and coverage |
| jsdom | 30.1.1 | dev | DOM for Vitest and the Mermaid check; needs Node 24.15 or later (open question 4) |
| @testing-library/react | 16.3.3 | dev | Component tests |
| @testing-library/dom | 10.4.2 | dev | Peer of the React testing library |
| @testing-library/jest-dom | 7.0.1 | dev | DOM matchers |
| @testing-library/user-event | 14.6.7 | dev | Interaction tests |
| msw | 2.15.0 | dev | Network mocking in tests |
| markdownlint-cli2 | 0.23.3 | dev | `make docs-check` (prompt requires it as a web devDependency) |
| mermaid | 12.0.0 | dev | Mermaid validation; 123 MB unpacked, open question 2 |

Deferred to phase 12, which uses them: React Router, TanStack Query, Radix UI, i18next, react-hook-form, zod, openapi-typescript, openapi-fetch, the icon set, and vitest-axe. vitest-axe needs a maintenance decision there: its latest stable release is 0.1.0 and the 1.0 line has been a prerelease since 2023.

## Tests to add

### Python unit

- `bootstrap/test_settings.py`: development defaults load with no environment and no `.env`; production refuses `DEMO_MODE=true`; production refuses each empty, short, or denylisted secret, one parameterized case per field; production accepts a fully valid set; the validation error names the field and never contains the secret value; `CORS_ALLOWED_ORIGINS` parses a comma-separated list; `litellm` in production requires the keys.
- `bootstrap/test_redaction.py`: one case per masked key; nested dicts and lists; key-substring matches (`access_token`, `set-cookie`); value patterns: email, a Colombian CC (`1.020.304.050`), a Mexican CURP, an Argentine DNI (`30.123.456`), a Brazilian CPF (`123.456.789-09`), a phone number, a long digit run; non-sensitive text, short numbers, ISO timestamps, and UUIDs stay intact; a Hypothesis property that no generated email address survives redaction.
- `bootstrap/test_logging.py`: end-to-end through `configure_logging`, captured output is valid JSON, carries the request id, and contains no sensitive value, including inside a formatted exception.
- `api/test_health_live.py`, `api/test_request_id.py` (generated when absent, echoed when valid, replaced when malformed), `api/test_problem_details.py` (404, 422 without the rejected input, 500 without internals, `application/problem+json`), `api/test_readiness.py` (fake checks: all ok, one failing, one timing out, none configured). These drive the app through the httpx ASGI transport with no sockets.
- `test_cli.py` in each package: `--help` exits 0 and lists `version`; `version` prints the name and version.
- `test_network_guard.py`: opening a TCP socket in a unit test raises `SocketBlockedError`.
- `test_import_contracts.py`: the negative control described above.
- `scripts/tests/unit/test_check_env_keys.py` (backlog item): set, unset, quoted, `export` form, inline comment, empty with comment, missing env file, name set only in the process environment, and sentinel values never appearing in stdout or stderr. It runs the script as a subprocess with a cleared environment and temporary files, never the real `.env`.
- `scripts/tests/unit/test_check_coverage_gates.py`: pass, fail, zero-statement prefix, and a missing gate table.
- `scripts/tests/unit/test_check_no_emoji.py`: detection of a generated emoji, a clean file, excluded paths, and binary files skipped.

### Python integration

`tests/integration/conftest.py` starts one session-scoped `postgres:16.15-alpine3.24` container through testcontainers, mounting `deploy/postgres/init`, with passwords generated by `secrets.token_urlsafe` at runtime. No credential is read from `.env` or written anywhere.

- `test_health_ready.py`: `/health/ready` returns 200 with `database: ok` against the real database as `bank_app`; returns 503 with no exception text when the database is configured but unreachable (a closed local port); `/health/live` returns 200 either way.
- `test_database_roles.py`: `bank_app` is not a superuser, has `NOBYPASSRLS`, owns no schema or table, cannot create tables in `app` or `public`, and can connect; `bank_owner` owns schema `app`. This is the executable proof of the init script.

### Web

- `App.test.tsx`: the shell renders a `main` landmark with the product name.
- `msw.test.ts`: a request to `/health/live` returns the handler's body, a per-test override works, and an unhandled request fails the test.
- `boundaries.test.ts`: the ESLint boundary policies reject forbidden imports and accept an allowed one.

### Docs tooling

- `scripts/checks/tests/check_mermaid.test.mjs`: valid diagrams pass, invalid ones fail with a file and line.

## Implementation increments and commits

Each increment runs its tests before committing. Messages follow CLAUDE.md section 12; scopes use the allowed list.

1. `build(infra): add uv workspace and shared python tool config`: root `pyproject.toml`, `.python-version`, `uv.lock`, root `conftest.py`, four package skeletons with typer CLIs and their tests.
2. `feat(api): add settings, redacting logger, and health endpoints`: bootstrap, ports, adapters, api modules, entry points, unit tests, layer READMEs.
3. `build(infra): add compose stack and postgres role bootstrap`: `docker-compose.yml`, `deploy/`, both `Dockerfile.dev`, integration tests.
4. `build(web): scaffold vite react app with lint and test tooling`: `apps/web`, `.nvmrc`, web tests, layer READMEs.
5. `build(infra): add coverage gates and repository check tests`: `check_coverage_gates.py` and the script tests, including the `check_env_keys.py` backlog tests.
6. `build(docs): add markdownlint and mermaid validation`: config, `check_mermaid.mjs`, its self-test.
7. `build(infra): add makefile and extend pre-commit hooks`: `Makefile`, `run_web_tool.sh`, autoupdated `.pre-commit-config.yaml`.
8. `ci: add ci workflow with python, web, guards, and audit jobs`.
9. `docs: add readme, docs index, architecture overview, and adrs 0001-0003`, plus `SECURITY.md`, `CONTRIBUTING.md`, and the pull request template.
10. `docs: record phase 01 progress and backlog`.

## Documentation

- Root `README.md`: purpose, repository map, prerequisites (uv, Python 3.12 through uv, Node 24.15 or later, Docker with Compose, pre-commit, gitleaks), quickstart (`make setup`, `make up`, `make check`), and links.
- `docs/README.md`: index of every document.
- `docs/architecture/overview.md`: a Mermaid flowchart of web, api layers, data platform, ml, evals, PostgreSQL, and the observability stack, with arrows in the dependency direction.
- ADRs in MADR format with context, options, decision, and consequences: 0001 record architecture decisions; 0002 uv workspace and hexagonal backend layers (including the entry-point placement, global mypy strictness, and the deferred `ml` extra); 0003 frontend layering and state rules. Index in `docs/adr/README.md`.
- Package and layer READMEs with responsibility, public interfaces, allowed importers, how to extend, and how to test. No placeholder text.
- `SECURITY.md`, `CONTRIBUTING.md`, `.github/pull_request_template.md` as in the prompt. No license file (open question 1).

## Backlog changes

Resolved and removed in the commit that resolves each:

| Item | Resolution |
|---|---|
| `make env-check` target | Added in increment 7 |
| pytest tests for `check_env_keys.py` | Added in increment 5 |
| Node 22 versus Node 24 | Node 24 LTS through `.nvmrc` (`24`) and `engines` (`>=24.15.0 <25`), subject to open question 4 |
| `pre-commit autoupdate` | Run in increment 7 |
| Guard scripts on uv-managed Python 3.12 | Hooks, Makefile, and CI call `uv run --no-project --python 3.12 python`, subject to open question 9 |

Added:

| Item | Owning phase |
|---|---|
| Choose the accessibility test library (vitest-axe maintenance status) and add the deferred frontend dependencies | 12 |
| Production PostgreSQL uses a non-superuser owner role for migrations, if open question 6 keeps the superuser owner in development | 16 |
| Grafana admin authentication for any non-local deployment of the `obs` profile | 16 |

## Verification

- `make setup`, then `make check`, from a clean clone with no `.env`.
- `docker compose up -d --wait postgres` becomes healthy, using throwaway passwords exported in the shell for the run (never written to `.env`), then `docker compose down -v`.
- `uv run bank-data --help`, `uv run bank-ml --help`, `uv run bank-eval --help`, and `uv run bank-agent --help`.
- `npm --prefix apps/web run build`.
- A deliberate violation of each gate (a layer import, a feature internal import, an emoji, an invalid Mermaid block) fails locally before being reverted, and the outputs go into the phase entry.

## Risks

- **Large dev dependencies.** mermaid (123 MB) and mypy (63 MB) exceed the 50 MB threshold. Both are dev-only and named by the prompt or CLAUDE.md. Needs approval.
- **Node engine mismatch.** jsdom 30 requires Node 24.15 or later; the local Node is 24.14.1. Mitigation: open question 4.
- **Newest majors not usable.** TypeScript 7 and ESLint 10 are ahead of their plugin ecosystems. Pinning 6.0.3 and 9.39.5 is deliberate; revisit when typescript-eslint and jsx-a11y catch up.
- **eslint-plugin-boundaries 7 uses a new policy API** with few examples. Mitigation: `boundaries.test.ts` proves the rules fire.
- **Empty layers make coverage gates trivially true.** Mitigation: the gate script reports `no statements yet` explicitly, and gates bite as soon as code lands.
- **`make check` needs Docker** for testcontainers. Docker is a documented prerequisite and the daemon is running; the failure message says so if not.
- **Version drift** between the pre-commit ruff rev and `uv.lock`. Mitigation: both pinned to 0.16.9, and the Makefile and CI use the locked ruff, so drift shows as a local mismatch rather than a CI surprise.
- **`filterwarnings = error`** can break on third-party deprecations after an upgrade. Mitigation: targeted ignores with reasons, never a blanket ignore.
- **File watching in containers on macOS** can miss events for Vite and uvicorn. Mitigation: polling fallbacks (`CHOKIDAR_USEPOLLING`, `WATCHFILES_FORCE_POLLING`) documented in the READMEs, off by default.
- **Global mypy strictness** may create friction with untyped libraries in later phases (dbt, MLflow). Mitigation: per-module import overrides, never relaxing the four strict layers.
- **pip-audit is stricter than the high-severity rule** because it has no severity filter. Accepted findings must be ignored explicitly with a reason.
- **Guard scripts through `uv run --python 3.12`** make uv a hard prerequisite for committing. It already is for everything else.

## Open questions

None of these blocks correctness, so nothing goes under "Blocked" in `docs/PROGRESS.md`. Each has a recommendation that stage 2 follows unless the human decides otherwise.

1. **License.** Which license, if any, should the repository carry? This plan does not choose one and adds no license file. The question goes into `docs/PROGRESS.md` as a pending human action.
2. **mermaid devDependency (123 MB unpacked, about 239 MB `node_modules` together with jsdom and markdownlint-cli2).** The prompt requires parsing with the `mermaid` package and forbids a headless browser; `@mermaid-js/parser` alone does not cover flowchart, sequence, state, or class diagrams. Recommendation: approve.
3. **mypy 2.3.1 (about 63 MB installed).** Required by CLAUDE.md section 3. Recommendation: approve.
4. **Node version.** Recommendation: upgrade the local Node to the latest 24.x LTS (24.21.0), pin `engines` to `>=24.15.0 <25`, and use `.nvmrc` `24` in CI and the web image. Alternative: stay on 24.14.1 and pin jsdom 29.1.1, which supports it.
5. **PostgreSQL in the CI `python` job.** The prompt names a service container. Recommendation: use testcontainers in CI as well, so CI and local runs share one fixture, the real init script, and the same image tag. GitHub-hosted Ubuntu runners have Docker. Alternative that follows the prompt literally: a `postgres:16.15-alpine3.24` service container with `POSTGRES_HOST_AUTH_METHOD=trust` (runner-local, ephemeral), a step that applies the same role SQL with a password generated and masked at runtime, and a fixture that uses those connection values when present. This splits the role script into a shell wrapper and a SQL file shared by both paths.
6. **PostgreSQL owner role.** Recommendation: in development and tests, the image's bootstrap role (`POSTGRES_ADMIN_USER`, `bank_owner`) is the owner, and the init script creates the application role and the owned schema. That needs no new variables. Its superuser status in development is accepted, with production hardening recorded for phase 16. Alternative: a separate superuser plus a `NOSUPERUSER` owner created by the init script, which needs a new `POSTGRES_SUPERUSER_PASSWORD` variable and a change to the phase 00 required-variable list.
7. **Coverage gates beyond CLAUDE.md.** CLAUDE.md names gates for six API layers and web features. Recommendation: also gate `bootstrap` (settings and redaction are security-critical) and the `bank_data`, `bank_ml`, and `bank_evals` sources at 80%.
8. **markdownlint rules MD032 and MD060.** The committed Markdown, including CLAUDE.md, has 216 findings under these two rules (compact tables and lists directly under bold lead-in lines). Recommendation: disable both in the repository config and leave CLAUDE.md untouched. Alternative: keep them on and reformat CLAUDE.md and the existing docs (whitespace and table-spacing changes only).
9. **Guard script interpreter.** Recommendation: hooks, Makefile, and CI run the stdlib guard scripts with `uv run --no-project --python 3.12 python`, which pins the interpreter without syncing the project environment. Alternative: keep `python3` in hooks and only use uv in the Makefile and CI.
10. **npm versus pnpm.** The project CLAUDE.md, the prompts, and the permission allowlist all use npm (`npm ci`, `npm audit`, `package-lock.json`), while the operator's global default is pnpm. Recommendation: npm, as the project specifies.

## Human actions

1. Answer the open questions, especially 1, 4, and 5, then approve this plan.
2. If open question 4 is answered as recommended, upgrade the local Node to the latest 24.x before stage 2 runs `npm ci`.
3. Creating `.env` stays a pending action from phase 00. Phase 01 does not need it: integration tests generate their own credentials, and only `make up` reads `.env`.
