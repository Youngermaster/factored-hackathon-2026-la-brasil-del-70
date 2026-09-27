# Progress

Continuity for the build lives in this file, not in chat history. Every phase adds an entry to the phase log and updates the current state.

## Current state

| Field | Value |
|---|---|
| Last completed phase | 01, monorepo scaffold and quality gates |
| Next phase | 02, domain model and contracts (`kit/prompts/02-domain-contracts.md`) |
| Blocked | None |
| Local EDA | Implemented, validated and completed for the local dataset snapshot |

Pending human actions (none blocks phase 02):

1. **License undecided; decide before submission.** No LICENSE file exists and the README says all rights are reserved until the team chooses. Tracked in `docs/BACKLOG.md` for phase 17.
2. Create `.env` from `.env.example` and fill in the organizer S3 values and local secrets. Never paste the values into a session. Then run `make env-check` and confirm every required name reports `set`. Phase 03 needs the S3 values; `make up` needs the two PostgreSQL passwords. `make check` does not need `.env`.
3. `.claude/settings.json` still allows `npm ci`, `npm install *`, and `npm run *`, and asks for `npx *`. Sessions did not change permission settings. If you want pnpm commands pre-approved, add equivalents such as `Bash(pnpm install *)`, `Bash(pnpm run *)`, `Bash(pnpm --dir apps/web *)`, and `Bash(pnpm exec *)`, and consider `Bash(pnpm dlx *)` under `ask`.
4. Run `/status` in Claude Code from the repository root and record the loaded setting sources in the phase 00 entry below.

## Phase log

### Local EDA and progressive viewer (2026-09-27)

Plan: [eda-local](plans/eda-local.md). Decision: [ADR 0004](adr/0004-local-eda-and-progressive-viewer.md).
This is an independent analysis deliverable; it does not mark the future S3/dbt or domain phases complete.

#### What changed

- Added `bank-data eda` commands, DuckDB profiling, conservative curation, lineage and relationship checks.
- Added content-addressed runs, transactional file checkpoints and independently published phase status.
- Added demand cubes, text repetition and temporal leakage diagnostics, local review sampling and workflow evidence.
- Added a local Streamlit viewer with aggregate process pages, Spanish and English labels and a Markdown report.
- Extended the viewer with a sanitized table explorer, a relationship graph and evidence-preserving
  workflow traffic lights; recorded the boundary in [ADR 0005](adr/0005-sanitized-eda-laboratory.md).
- Added optional `eda` and `eda-ui` dependencies, Make targets, synthetic tests and CI installation of the extras.
- Corrected two existing whitespace issues in kickoff notes so the documentation gate passes.

#### Validation

- `make check` passes: 170 unit tests, 30 integration tests, 17 web tests and all 10 coverage gates.
- Data-platform line coverage: 95.8 percent before the laboratory extension. All eight Streamlit
  pages pass synthetic-data checks; the latest data-platform suite has 36 passing tests.
- Actual inventory and profile pages pass AppTest; the local HTTP health endpoint returns `ok`.
- A built wheel includes the JSON contracts and the viewer. Gitleaks reports no leaks.
- Streamlit requires `websockets<17`; the shared lockfile moves that dependency from 17.1 to 16.1.1.
  All other previously locked versions are unchanged, and backend tests pass.

#### Full-data run

Run `372ff8010bafd0b4d802` loaded all 7,671 CSV files with no parse errors: 23,495,188 rows.
All five phases completed: inventory, profiling, curation, analysis and aggregate report generation.
The prior run `d970e99d520f204fc3ef` was interrupted during ingestion and is explicitly marked failed.
Original input files are unchanged. Results remain under the ignored `data/eda/` tree.

The curated layer retains 23,471,159 structurally eligible rows; it excludes 24,029 transcripts
with a missing required duration. The shareable aggregate findings are recorded in
[analysis/RESULTS.md](analysis/RESULTS.md).

The full profile found no duplicate primary keys or identical parsed rows in this local snapshot.
It found 24,029 missing required transcript durations, 772 resolved/closed complaints without
resolution dates, 1,040 claimed amounts without currencies, six extra repeated product numbers
and 13 extra repeated employee codes. Text repetition is evaluated separately from duplicate events.

#### How to use

See [the EDA guide](analysis/EDA.md): `make eda-setup`, `make eda`, then `make eda-ui`.
The viewer binds to localhost. Process pages expose completed aggregate artifacts; the laboratory
adds bounded samples using an explicit low-risk allowlist, with free text and sensitive values removed.

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
