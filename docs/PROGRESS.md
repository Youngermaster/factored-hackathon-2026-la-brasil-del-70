# Progress

Continuity for the build lives in this file, not in chat history. Every phase adds an entry to the phase log and updates the current state.

## Current state

| Field | Value |
|---|---|
| Last completed phase | 02, domain model, ports, and contracts |
| Next phase | 02b, multi-workflow contracts (`kit/prompts/02b-multi-workflow-contracts.md`), then 08, then 03 once `.env` exists |
| Blocked | None |

Pending human actions (none blocks phase 03 except item 2, which phase 03 needs for the S3 download):

0. **Review the phase 02 domain model and handoff schema before phases 05, 06, and 09 start.** The summary is in the phase 02 entry below; contracts change cheaply now and expensively later.

1. **License undecided; decide before submission.** No LICENSE file exists and the README says all rights are reserved until the team chooses. Tracked in `docs/BACKLOG.md` for phase 17.
2. Create `.env` from `.env.example` and fill in the organizer S3 values and local secrets. Never paste the values into a session. Then run `make env-check` and confirm every required name reports `set`. Phase 03 needs the S3 values; `make up` needs the two PostgreSQL passwords. `make check` does not need `.env`.
3. `.claude/settings.json` still allows `npm ci`, `npm install *`, and `npm run *`, and asks for `npx *`. Sessions did not change permission settings. If you want pnpm commands pre-approved, add equivalents such as `Bash(pnpm install *)`, `Bash(pnpm run *)`, `Bash(pnpm --dir apps/web *)`, and `Bash(pnpm exec *)`, and consider `Bash(pnpm dlx *)` under `ask`.
4. Run `/status` in Claude Code from the repository root and record the loaded setting sources in the phase 00 entry below.

## Phase log

### Phase 02: domain model, ports, and contracts (2026-09-26)

Plan: `docs/plans/phase-02.md`, approved by the human on 2026-09-26 with every open-question recommendation (trust keyed by session lineage; length caps plus a single-paragraph summary for handoff text; `FakeLLM` in `bank_agent.testing` with the `LLM_PROVIDER=fake` wiring left to phase 08; client-supplied UUID turn ids; `first_name` as the only personal data in `Customer`; channels `web_chat`, `agent_console`, `evaluation_harness`; the scenario model in `bank_evals`; the staleness test as a unit test; the case lifecycle table; risk thresholds in the domain; intake-time complaint fields only).

#### What was done

| Commit | Change |
|---|---|
| `650ca1c` | The approved plan |
| `086e38b` | Value objects (`Money`, `Currency`, `ExchangeRate`, `Country`, `Language`, `Locale`, typed identifiers, `SourceRef`, `MaskedNumber`, `AuthLevel`, `Role`, `Channel`, `AccessContext`), the error taxonomy, ADR 0004 |
| `cefecf4` | Entities (`Customer`, `Product`, `Transaction`, `HistoricalComplaint`, `DisputeCase`, `Session`, `Conversation`, `Turn`), identity challenges, `TrustState`, workflow concepts (`Intent`, `TransactionDescriptor`, `DisputeReason`, `Decision`, `ActionRequest`, `ActionResult`, `Verification`, `Outcome`), `AssistantResponse` and `TurnResult`, the `Handoff` and `ExecutionRecord` models, `FixedClock`, ADR 0005 |
| `fe0761f` | Every port (repositories with reader Protocols, unit of work, audit log, session store, identity, determinism, LLM client, prompt registry, policy repository, retriever, router, resolver, language detector, model registry, telemetry); `SystemClock`, `RandomIdGenerator`, `NoopTelemetry`; the remaining test doubles; two import-linter contracts for `bank_agent.testing`; a 90% coverage gate for it |
| `aa0933d` | In-memory adapters for every repository port, the unit of work, and the session store; the shared contract suites; the port conformance test |
| `cf438ea` | `bank_evals.scenarios.model.Scenario` (scenario v1); `bank-evals` depends on `bank-agent` |
| `d169203` | `scripts/generate_contracts.py`, `make contracts`, the five schemas in `contracts/schemas/`, the staleness and no-reasoning-field tests, `contracts/README.md`, ADR 0006 |
| `b106405` | `api/domain_problems.py`: domain error families mapped to problem types, installed by default |
| `f8e5df8` | Whitespace fix in `docs/plans/kickoff-notes.md` (merged from the team repository), so `make docs-check` passes |
| `51bb92f` | `docs/architecture/domain-model.md`, `docs/architecture/ports-and-adapters.md`, README and index updates |

#### Domain model summary for review

- **Money:** `Decimal` amount plus explicit currency; floats rejected; arithmetic only within one currency and exact (an inexact result raises); conversion only through `ExchangeRate`; banker's rounding only in `rounded()`. JSON carries amounts as strings.
- **Identity and access:** repositories are bound to an `AccessContext` (role plus customer or staff id) through a unit of work, and no repository method accepts a customer id; another customer's record behaves like a missing one. Sessions store expiry instants (idle, absolute, step-up window) and answer every expiry question from an instant; the raw token never enters the domain (stores look up by digest).
- **Trust state:** append-only events keyed by session lineage (kept across rotation and re-authentication into the same conversation), stored outside the turn's transaction; the risk tier (low, elevated, high) never decreases.
- **Dispute case lifecycle:** `opened` to `in_review`, `escalated`, or `rejected`; `in_review` to `resolved`, `rejected`, or `escalated`; `escalated` to `in_review`, `resolved`, or `rejected`; `resolved` and `rejected` are terminal; no `opened` to `resolved`.
- **Success needs evidence:** a positive `Verification` needs an evidence reference, a verified action status in a response needs evidence, and a verified action in a handoff must have executed and been confirmed.
- **Personal data:** `Customer` carries only `first_name`; document numbers, phones, emails, and addresses stay in the phase 05 identity adapter. Fraud label and score are `Internal`. Customer and record text is `UntrustedText`.

#### Handoff schema summary for review (`contracts/schemas/handoff.v1.json`)

`schema_version`, `handoff_id`, `created_at`, `conversation_ref`, `case_ref`, `state_at_escalation`, `language` (es or pt), `jurisdiction`, `customer_ref` (internal id only), `auth` (level, expires_at), `request` (summary of at most 500 characters on one paragraph, intent), `verified_facts` (fact plus a mandatory `table:id` source, at most 20), `actions_taken` (action, target, confirmed, status executed or failed or unknown, verification verified or not_verified or mismatch, evidence), `policy_basis` (`clause_id@version`), `escalation_reason` (code from a fixed list, detail), `open_questions` (at most 10), `customer_sentiment`, `priority`, `sla_due`. Unknown keys are rejected at every level, which is how transcript fields are refused, and no output contract has a reasoning field.

#### Decisions

- [ADR 0004](adr/0004-money-and-currency-handling.md): money and currency handling.
- [ADR 0005](adr/0005-trust-state-append-only.md): trust state as append-only evidence with a monotonic risk tier.
- [ADR 0006](adr/0006-handoff-and-execution-record-contracts.md): handoff and execution record contracts, with no chain-of-thought field.
- No third-party dependency was added. `bank-evals` gained a uv workspace dependency on `bank-agent` (lockfile change only).

Deviations from the plan text, found during implementation:

- `InvariantViolation` is named `InvariantViolationError` (ruff N818), and the planned `InvalidMoneyError` became `MoneyPrecisionError`, because construction failures surface as Pydantic `ValidationError` and the only behavioral money failure is an inexact result.
- `SessionStore.save(session)` replaces the planned `touch`, `set_step_up`, and `revoke`: the domain methods (`touched`, `with_step_up`, `revoked`) build the new session and the store persists it, so the rules live in one place.
- `DomainModel.evolve` was added because `model_copy(update=...)` skips validation; every entity change goes through it.
- Serialization-mode schemas mark every field as required (`json_schema_serialization_defaults_required`), because serialized documents always carry every field.
- Idempotent case creation compares the request (transaction, reason, amount) rather than the stored case, so replaying a request after the case moved on still returns it.
- `RandomIdGenerator` uses 128 random bits in hex rather than base32.
- The plan's test that validates a handoff against the generated schema dictionary needs a JSON Schema validator, which is not installed; the schema is generated from the model that validates the handoff, and adding a validator is in `docs/BACKLOG.md` for phase 09.
- Shared test support lives in `services/api/tests/bank_agent_builders.py` and `services/api/tests/bank_agent_contracts.py` (unique module names, importable under `--import-mode=importlib`).
- A conformance test (not in the plan) checks through mypy that every implementation satisfies its port and at runtime that every port docstring states preconditions, postconditions, errors, and isolation; the phase 01 `ReadinessCheck` docstring gained the missing sections.
- The work landed in 9 commits instead of the planned 12: the entity, workflow, and contract models share one commit because their tests share builders.
- The human merged `docs/plans/kickoff-notes.md` from the team repository during the phase (commit `8d4123f`); only its whitespace was changed.

#### How to verify

```bash
make check                                                      # needs Docker running; never reads .env
make contracts && git diff --exit-code contracts/               # schemas are current
uv run pytest services/api/tests/contracts -q                   # every memory adapter passes its suite
uv run pytest services/api/tests/unit/domain -q                 # domain unit and property tests
uv run lint-imports                                             # five contracts kept
```

Results recorded in this phase:

| Check | Result |
|---|---|
| `make check` | Exit 0 |
| Python tests | 612 unit tests (including 75 contract-suite tests on the memory backend) and 11 integration tests pass |
| Coverage gates | All 11 pass: domain 99.6%, ports 100%, adapters 100%, api 97.4%, bootstrap 100%, testing 100%, evals 100%; policy and application report `no statements yet` |
| Import contracts | 5 kept, each with a negative control |
| Docs check | markdownlint 0 issues; 10 mermaid blocks in 46 files parse |
| Guards | No emoji; attribution clean; gitleaks found no leaks |

#### Known limitations

- Only the memory backend runs the repository contract suites; DuckDB readers (phase 03) and PostgreSQL adapters (phase 05) must be added to `READ_BACKENDS` and `WRITE_BACKENDS`.
- The router, resolver, and language detector suites run only against scripted fakes until phases 09 and 10.
- Ports for identity, prompts, policy, retrieval, and the model registry have no implementation yet (phases 05 to 10).
- In-process ports are synchronous; a remote implementation would need an async variant.
- A newer minor version of a contract fails an older validator because unknown keys are rejected; producers and consumers must upgrade together (documented in `contracts/README.md`).
- Superseded on 2026-09-26: the human chose four workflows (`account_inquiry`, `card_support`, `dispute`, `credit`); CLAUDE.md section 1 records the decision, and phase 02b extends these contracts additively.

#### Next phase

Phase 03, data platform (`kit/prompts/03-data-platform.md`). It needs the organizer S3 values in `.env` (pending action 2). Phases 05, 06, and 09 should wait for the team's review of this phase's domain model and handoff schema.

### Phase 01: monorepo scaffold and quality gates (2026-09-26)

Plan: `docs/plans/phase-01.md`, approved with the decisions listed at its top (no license yet; mermaid, jsdom, and mypy approved despite the 50 MB rule; Node 24.21.0; pnpm instead of npm; testcontainers in CI and locally; `bank_owner` as the development owner; extra coverage gates; MD032 and MD060 off; guard scripts on uv-managed Python 3.12).

#### What was done

Ten commits, `f40f180` to the commit that adds this entry:

| Commit | Change |
|---|---|
| `f40f180` | uv virtual workspace root with shared ruff, mypy, import-linter, pytest, coverage, and bandit configuration; the four packages with typer CLIs (`bank-agent`, `bank-data`, `bank-ml`, `bank-eval`) exposing `version` and `--help`; the root `conftest.py` that classifies tests by directory and blocks the network for unit tests |
| `728adac` | `bank_agent`: layer packages with READMEs; `bootstrap/settings.py` (five settings classes, production rules); `bootstrap/logging.py` (structlog JSON with a redaction processor, also for uvicorn and other standard-library loggers); `bootstrap/container.py`; `ports/health.py`; the PostgreSQL readiness adapter; `api/` (app factory, request id middleware, RFC 9457 problem registry, `/health/live`, `/health/ready`); entry points `asgi.py` and `cli.py`; unit tests, including a negative control for the import-linter contracts |
| `bb32902` | `apps/web`: Vite 8, React 19, TypeScript 6 strict, Tailwind CSS v4, ESLint 9 (typescript-eslint strict type-checked, react-hooks, jsx-a11y strict, boundaries), Prettier, Vitest with jsdom, Testing Library, and MSW; layer READMEs; the neutral shell; a fixture-based boundary test |
| `bcd45ac` | `docker-compose.yml` (postgres always on; `api`, `web`, `obs`, and `ml` profiles; every image pinned; ports on 127.0.0.1); `deploy/postgres/init/10-roles.sh`; observability configs; both `Dockerfile.dev`; integration tests for readiness and database roles through testcontainers |
| `ec3e2a4` | `scripts/checks/check_coverage_gates.py`; tests for `check_env_keys.py`, the gate checker, and the emoji check |
| `073b3e3` | `.markdownlint-cli2.jsonc`, `scripts/checks/check_mermaid.mjs`, and its `node:test` self-test |
| `7fe0faa` | `Makefile` (help, setup, up, down, check, lint, format, typecheck, test-unit, test-integration, test-web, env-check, docs-check); extended and autoupdated `.pre-commit-config.yaml`; `scripts/hooks/run_web_tool.sh` |
| `7310d43` | `.github/workflows/ci.yml` with the python, web, guards, and audit jobs |
| `a075f45` | CLAUDE.md switched from npm to pnpm (human-authorized): the frontend stack line, the supply-chain rule, and the note that later prompts saying npm or npx mean pnpm or `pnpm dlx` |
| `edd8ff3` | Root README, `docs/README.md`, `docs/architecture/overview.md`, ADRs 0001 to 0003 with the index, `SECURITY.md`, `CONTRIBUTING.md`, and the pull request template |

The five phase 00 backlog items owned by phase 01 are resolved and removed from `docs/BACKLOG.md`: the `make env-check` target, pytest tests for `check_env_keys.py`, the Node version decision (Node 24 LTS through `engines` `>=24.15.0 <25` and `.nvmrc` `24`), `pre-commit autoupdate`, and running the guard scripts on the uv-managed Python 3.12.

#### Decisions

- [ADR 0001](adr/0001-record-architecture-decisions.md): record architecture decisions in MADR format.
- [ADR 0002](adr/0002-uv-workspace-and-hexagonal-backend.md): uv workspace monorepo and hexagonal backend layers, including the entry points outside the layers, global strict mypy, and per-layer coverage gates.
- [ADR 0003](adr/0003-frontend-layering-and-state.md): frontend layering, state rules, and ESLint enforcement.
- Package manager: pnpm 10.33.0 (human decision), pinned through `packageManager`, with `apps/web/pnpm-workspace.yaml` declaring that the lifecycle scripts of `msw` (browser worker copy) and `unrs-resolver` (fallback binary download) are not needed.
- Large dev dependencies approved by the human despite the 50 MB rule: mermaid 12.0.0 (123 MB unpacked; with jsdom and markdownlint-cli2 the docs tooling adds about 240 MB to `node_modules`, whose total is about 450 MB) and mypy 2.3.1 (about 63 MB installed).
- TypeScript 6.0.3 instead of 7.0.2 (typescript-eslint 8.70.1 requires below 6.1) and ESLint 9.39.5 instead of 10.x (eslint-plugin-jsx-a11y supports ESLint 9 at most).
- The development and test owner role is the image bootstrap role `bank_owner`; a non-superuser production owner is deferred to phase 16.

Dependencies added, all permissively licensed and maintained; exact versions are in `uv.lock` and `apps/web/pnpm-lock.yaml`:

- Python runtime (`bank-agent`): fastapi 0.141.1, pydantic 2.13.5, pydantic-settings 2.15.0, uvicorn[standard] 0.54.0, structlog 26.1.0, typer 0.27.2, sqlalchemy[asyncio] 2.1.1, asyncpg 0.31.0. The other three packages depend on typer only.
- Python dev group: pytest 9.1.1, pytest-asyncio 1.4.0, pytest-socket 0.8.1, pytest-cov 7.1.0, hypothesis 6.168.1 (MPL-2.0, dev only), testcontainers 4.15.0, httpx 0.28.1, ruff 0.16.9, mypy 2.3.1, import-linter 2.15, bandit 1.9.4, pip-audit 2.10.1.
- Web: react and react-dom 19.3.0; dev: vite 8.3.1, @vitejs/plugin-react 6.1.1, typescript 6.0.3, tailwindcss and @tailwindcss/vite 4.3.3, eslint and @eslint/js 9.39.5, typescript-eslint 8.70.1, eslint-plugin-react-hooks 7.1.1, eslint-plugin-react-refresh 0.5.7, eslint-plugin-jsx-a11y 6.10.2, eslint-plugin-boundaries 7.2.0, eslint-import-resolver-typescript 4.4.5, eslint-config-prettier 10.1.8, globals 17.12.0, prettier 3.9.9, vitest and @vitest/coverage-v8 5.0.2, jsdom 30.1.1, Testing Library (react 16.3.3, dom 10.4.2, jest-dom 7.0.1, user-event 14.6.7), msw 2.15.0, markdownlint-cli2 0.23.3, mermaid 12.0.0, @types/react and @types/react-dom 19.3.0, @types/node 24.19.0.

Deviations from the plan text, found during implementation:

- mypy runs once over every package with `explicit_package_bases` instead of once per package, because per-package runs still collided on `services/api/tests/conftest.py` and `services/api/tests/integration/conftest.py`. The root `conftest.py` is checked in a second run.
- `ApiConfig` is passed to `create_app` next to the provider instead of being a `ServiceProvider` property, because `bootstrap` may not import `api`, so the container cannot build it; `bank_agent.asgi` builds it from settings.
- The boundary test lives in `apps/web/tooling/boundaries.test.ts` (with a fixture tree beside it) rather than `src/test/`, because it uses Node APIs that the browser tsconfig does not include.
- The "features only through `index.ts`" rule is the last policy of `boundaries/dependencies` (`fileInternalPath: '!(index.ts)'`) instead of the separate `boundaries/entry-point` rule, which is deprecated in eslint-plugin-boundaries 7.
- Shared test doubles live in `services/api/tests/bank_agent_test_support.py`, importable through the pytest `pythonpath` setting, because `--import-mode=importlib` does not put test directories on the path.
- The compose `api` service reads `.env` optionally and receives the database values explicitly, so `docker compose config` works from shell variables alone.
- `pre-commit autoupdate` selected gitleaks v8.30.0 for the hook; the gitleaks binary used by `make check` and CI is 8.30.1.
- Two bandit findings in `scripts/checks/check_no_emoji.py` (importing `subprocess`, running `git` from PATH with a fixed argument list) carry `nosec` annotations with a justification comment.

#### How to verify

```bash
make setup
make check                                   # needs Docker running; never reads .env
uv run bank-data --help && uv run bank-ml --help && uv run bank-eval --help && uv run bank-agent --help
pnpm --dir apps/web run build
POSTGRES_ADMIN_PASSWORD="$(openssl rand -hex 16)" POSTGRES_APP_PASSWORD="$(openssl rand -hex 16)" \
  docker compose up -d --wait postgres       # becomes healthy; then: docker compose down -v
```

Results recorded in this phase:

| Check | Result |
|---|---|
| `make setup` then `make check` in a fresh clone with no `.env` | Both exit 0 |
| Python tests | 170 unit tests and 11 integration tests pass |
| Coverage gates | All 10 pass: ports, adapters, bootstrap, and the three CLI packages at 100%, api at 97.3%; domain, policy, and application report `no statements yet` |
| Web tests | 17 tests pass (shell, MSW setup, boundary policies); `pnpm run build` succeeds |
| Docs check | markdownlint 0 issues; 5 mermaid blocks in 37 files parse |
| Guards | No emoji; attribution clean for `HEAD`; gitleaks found no leaks |
| Audits | pip-audit and `pnpm audit --prod --audit-level high`: no known vulnerabilities |
| Workflow lint | actionlint 1.7.7 reports no findings for `ci.yml` |
| Compose, postgres | Healthy with throwaway passwords; `bank_app` is not a superuser and has no `BYPASSRLS`; `app` is owned by `bank_owner` |
| Compose, all profiles | `api` healthy and `/health/ready` returns `database: ok` with JSON logs carrying request ids; the web dev server serves and proxies `/health/live`; Jaeger, Prometheus (scraping the collector), Grafana, and MLflow respond; stack removed with `down -v` |
| Deliberate violations | A domain module importing the API breaks two import-linter contracts; a page importing a feature internal fails ESLint; an emoji fails the emoji check; a malformed diagram fails the Mermaid check with its file and line |

#### Known limitations

- The CI workflow has not run on GitHub yet, because nothing was pushed. It passed actionlint, and every step mirrors a local `make check` step that passes.
- The domain, policy, and application layers are empty, so their coverage gates are satisfied trivially and say so explicitly.
- The web shell renders only the product name; i18next, the router, TanStack Query, Radix, forms, the generated API client, and vitest-axe arrive in phase 12.
- Readiness checks only the database; health endpoints do not yet reflect other dependencies (phase 15).
- The web development image installs pnpm through corepack at build time and runs `pnpm install` at container start, so both need network access.
- Hot reload inside containers on macOS may need polling; the fallbacks are documented in `deploy/README.md`.

#### Next phase

Phase 02, domain model and contracts (`kit/prompts/02-domain-contracts.md`), in plan mode.

### Phase 00: bootstrap and guardrail verification (2026-09-26)

Plan: `docs/plans/phase-00.md`.

#### What was done

- Verified the toolchain, skills, attribution settings, ignore rules, and hooks without installing anything.
- Ran the guard self-tests on scratch files and recorded the outputs below.
- Fixed a `.gitignore` defect: `data/` excluded the directory itself, so the existing `!data/.gitkeep` negation had no effect. The rule is now `**/data/*`, which still ignores the contents of every `data` directory at any depth. Added `data/.gitkeep`.
- Added `scripts/checks/check_env_keys.py`, which reports `set` or `unset` for every name documented in `.env.example`, never a value, and exits 1 when a required name is unset.
- Created this file, `docs/BACKLOG.md`, and `docs/plans/`.

#### Environment report

| Tool | Version | Notes |
|---|---|---|
| git | 2.55.0 | |
| uv | 0.11.17 | |
| Python | 3.12.13, uv-managed | System `python3` is Homebrew 3.14.7; the guard scripts are stdlib-only and run under it through pre-commit |
| Node | v24.14.1 | Newer than the preferred 22 LTS; see `docs/BACKLOG.md` |
| npm | 11.11.0 | |
| Docker | 29.8.0, daemon running | |
| Docker Compose | v5.5.1 | |
| pre-commit | 4.6.2 | pre-commit and commit-msg hooks installed; `core.hooksPath` unset |
| gitleaks | 8.30.1 | The pre-commit hook pins v8.21.2 until phase 01 runs `pre-commit autoupdate` |
| AWS CLI | 2.36.26 | Optional; ingestion uses boto3 |
| go | 1.26.1 | Builds the gitleaks pre-commit hook |
| libomp | 23.1.2 | LightGBM prerequisite |

Skills present under `.claude/skills/`: `design-taste-frontend`, `minimalist-ui`, `full-output-enforcement`.

Settings: `.claude/settings.json` sets `attribution.commit` and `attribution.pr` to empty strings and `attribution.sessionUrl` to `false`. A gitignored `.claude/settings.local.json` allows `git commit *`; the project deny rules for `--no-verify` and `-n` still apply. Loaded setting sources from `/status`: pending human action.

Ignore rules: `git check-ignore -v` confirms `.env`, `.env.*` except `.env.example`, `data/` contents, `kit/`, `mlruns/`, `node_modules/`, `dist/`, `.coverage`, `coverage.xml`, `htmlcov/`, `apps/web/coverage/`, and `*.duckdb`. Nothing under `kit/` is tracked; the only tracked file under `data/` is `data/.gitkeep`.

Secret hygiene: `.env` does not exist yet (checked for existence only, never read). Running `python3 scripts/checks/check_env_keys.py` in the repository prints the notice `.env not found; checking the process environment only`, reports all 9 required names as unset, and exits 1.

#### Guard self-test results

| Test | Command | Result |
|---|---|---|
| Attribution stripping | `python3 scripts/hooks/strip_ai_attribution.py msg.txt` on a scratch message containing `Co-Authored-By: Claude Opus <noreply@anthropic.com>` and `Generated with [Claude Code](https://claude.com/claude-code)` | Printed `strip-ai-attribution: removed attribution lines from the commit message`, exit 0. The file kept only the subject and body; a grep for either line found 0 matches |
| Emoji check, failing case | `python3 scripts/checks/check_no_emoji.py emoji.txt` on a file written by Python with U+1F600 | `emoji.txt:1:7: emoji character U+1F600 is not allowed`, `check-no-emoji: 1 emoji character(s) found`, exit 1 |
| Emoji check, passing case | `python3 scripts/checks/check_no_emoji.py CLAUDE.md` | exit 0 |
| Attribution history | `scripts/checks/check_no_ai_attribution.sh` | `check-no-ai-attribution: clean for range 'HEAD'`, exit 0 |
| All hooks | `pre-commit run --all-files` | gitleaks, large files, private key, merge conflict, end of file, trailing whitespace, and emoji hooks all passed |
| Secrets in history | `gitleaks git --redact .` | no leaks found |

Environment key check self-tests, all with scratch env files and an emptied process environment, never the real `.env`:

| Case | Result |
|---|---|
| Every required name set to a unique sentinel, mixing quoted, `export`, and inline-comment forms | exit 0, `all 9 required variable(s) set`, 0 sentinel strings in the output |
| `SESSION_SECRET` empty with a trailing comment, `CSRF_SECRET` absent | exit 1, both reported `unset`, `2 of 9 required variable(s) unset`, 0 sentinel strings in the output |
| Env file does not exist | notice printed, process environment used, exit 1 |
| Name set only in the process environment | reported `set`, value not printed |

#### Decisions

- `.gitignore` uses `**/data/*` instead of `data/` so that `data/.gitkeep` can be tracked. Approved by the human with the phase plan. No ADR: this is a correction, not a choice between alternatives.
- The required variable set for `check_env_keys.py` is the S3 values, both PostgreSQL passwords, and the session and CSRF secrets. The LLM keys stay optional while `LLM_PROVIDER=fake`. Approved by the human.
- No dependencies were added.

#### How to verify

```bash
pre-commit run --all-files
python3 scripts/checks/check_no_emoji.py
scripts/checks/check_no_ai_attribution.sh
gitleaks git --redact .
git ls-files kit data          # expected: data/.gitkeep only
python3 scripts/checks/check_env_keys.py
```

#### Known limitations

- `make check` does not exist until phase 01, so this phase used the commands above as its substitute.
- `check_env_keys.py` has manual self-tests only; automated tests are in `docs/BACKLOG.md` for phase 01.
- `/status` output and `.env` creation are pending human actions.

#### Next phase

Phase 01, monorepo scaffold and quality gates (`kit/prompts/01-scaffold.md`), in plan mode.
