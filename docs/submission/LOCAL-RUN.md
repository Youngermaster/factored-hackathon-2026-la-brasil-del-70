# Run everything locally: a verified walkthrough

Every command below was run in order on a fresh clone (`git clone`, then a branch), following [README.md](../../README.md) and [AGENTS.md](../../AGENTS.md) literally, on 2026-09-30. The timings are from that run, on a laptop whose uv, pnpm, Docker, and Playwright caches were already warm; a machine that downloads everything for the first time spends a few more minutes in `make setup`, the first `make up` (the PostgreSQL image), and the first image build. The [verification log](#verification-log) at the end lists each check and its result. Every friction point found on the way has a row in [Troubleshooting](#troubleshooting).

## Prerequisites

Versions found on the verification machine (Apple silicon, macOS, Darwin 27.0.0):

| Tool | Version used | Required | Notes |
|---|---|---|---|
| uv | 0.11.17 | 0.11.17 or later | Installs Python 3.12 from `.python-version` |
| Node.js | 24.21.0 through nvm | 24.15 or later, below 25 | nvm's default on this machine is 24.14.1, which is too old: `make setup` then stops at `pnpm install` with an engines error. Run `nvm use 24` (or `nvm use` in the repository) in every new shell |
| pnpm | 10.33.0 | 10.33 | Pinned by `packageManager` |
| Docker | 29.8.1 (Docker Desktop), Compose v5.5.1 | Compose v2 or later | Must be running |
| pre-commit | 4.6.2 | Any recent | `make setup` installs the hooks |
| gitleaks | 8.30.1 | Any recent | Used by the hooks and `make check` |
| make | GNU Make 3.81 (`/usr/bin/make` on macOS) | GNU make | Works; 3.81 ignores `.SHELLFLAGS`, so a failing command inside a pipe does not stop a target the way it does on GNU make 3.82 or later |
| Ollama | 0.34.4 with `qwen2.5:7b-instruct` (Q4_K_M, 4.7 GB) | Only for the local model | `ollama pull qwen2.5:7b-instruct`; serves on `http://localhost:11434` |
| Chromium for Playwright | `chromium-1243` (Playwright 1.63.0) | Only for `make csp-check` and browser scripts | pnpm does not download it: `pnpm --dir apps/web exec playwright install chromium`, once |

No organizer credentials and no model key are needed.

Non-interactive shells (scripts, IDE terminals, agents) do not load nvm. Start each one with:

```bash
export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 24
node -v                                   # v24.15 or later
```

### A second checkout on the same machine

`docker-compose.yml` names its project `bank-agent`. A second clone or worktree that runs `make up` would therefore take over the first checkout's PostgreSQL container and volume (and the volume keeps the first checkout's passwords, so the second one's `make db-upgrade` fails to sign in). If another checkout's dev stack is running, or port 5432 is taken, export a project name and a port in every shell of the second checkout; Compose and the service settings both prefer the environment over `.env`:

```bash
export COMPOSE_PROJECT_NAME=bank-agent-e2e POSTGRES_PORT=5442
```

The verification run used exactly these two values beside a running main checkout, without touching it.

## 1. The development path (fake model, committed sample)

| Step | Command | Time | What you should see |
|---|---|---|---|
| Env file | `make env` | under 1 s | `make-env: wrote .env with 4 freshly generated development secret(s)`; `.env` has mode 600 |
| Dependencies | `make setup` | 5 s warm | uv sync, `pnpm install`, then `pre-commit installed at .git/hooks/pre-commit` and `commit-msg` |
| PostgreSQL | `make up` | 6 s | `Container ...-postgres-1 Healthy` |
| Migrations | `make db-upgrade` | 4 s | `schema at revision 0013` |
| Data | `make pipeline` | 49 s | `source=sample ... loaded=783 ... rows_loaded=2470`, `built source=sample`, `tests and freshness passed` |
| Seed | `make seed` | 1.5 s | 12 `persona <id>: CLI-...` lines, then `customers: 59`, `staff_members: 2`, `dispute_cases: 1`, `credit_applications: 1` |
| Settings | `make env-check` | under 1 s | One line per variable (`set` or `unset`), ending `all 4 required variable(s) set`; never a value |

`make seed` also migrates, so after a volume reset `make db-upgrade` is not needed. The committed sample has 59 customers, fewer than `SEED_CUSTOMERS=200`; that is expected.

Then two terminals (each with Node 24 and, for a second checkout, the two exports above):

```bash
DEMO_MODE=true uv run --frozen uvicorn bank_agent.asgi:create_app --factory --reload   # API on 127.0.0.1:8000
VITE_DEMO_MODE=true pnpm --dir apps/web run dev                                         # web on localhost:5173
```

The API logs `Application startup complete.` within about 5 seconds; Vite prints `ready in ~800 ms`. Health: `curl -s localhost:8000/health/ready` answers `{"status":"ready","checks":{"database":"ok"}}`, and `/health/details` shows level `L0` with `llm_primary: disabled` (the fake provider). There is no `/healthz` or `/v1/health`.

Open `http://localhost:5173`. The browser's language picks the interface language; the Preferences button (gear icon) changes the language and region and the theme.

## 2. What to look at in the browser

Start at `/demo` (the demo guide): it lists, per workflow, the normal, ambiguous or unsupported, and escalation paths in Spanish and Portuguese, with the persona and the exact messages. All 16 scenarios were played in Spanish from a browser in English and in Portuguese from a browser in Portuguese (Brazil), with no console error and no failed request. With the fake provider every turn answers in about 0.7 s.

**Sign-in.** Click a profile under "Customers" (or "Bank staff"); the page shows a 6-digit demo code under "Demo code"; type it and press Verify. The four profiles under "Only with the full data" do not exist on the committed sample, so do not use them. Signing in more than about three times a minute from one address answers "Too many requests in a row. Wait a moment and try again." (the auth limit is 10 requests per minute and a sign-in costs three); wait a minute, or raise `RATE_LIMIT_AUTH_PER_MINUTE` and `RATE_LIMIT_SESSION_AUTH_PER_MINUTE` in the API's environment for a fast run through every persona.

**The chat and its record.** Beside the chat, the execution record (glass box) shows per turn: the state change (for example `START -> BALANCES`), the outcome, the understanding models (intent with its confidence, language), the model prompts (with the fake provider: "unavailable: the deterministic path was used"), the policy decisions per state with rule counts, the clauses with their text, the tool calls with latency and result, and the versions, latency, tokens, and cost. "Full record" opens the same record on its own route, `/glass-box/<conversation id>`. The conversation reference is printed at the top of the chat; copy it for the evaluator view.

| Workflow | Persona | What to check |
|---|---|---|
| Accounts and payments | `acc-mx-accounts` | Balances name the as-of date ("con datos al 17 de junio de 2026"); "my transfer" without details asks for amount, date, or recipient; a transfer request abstains with cited policies; "Mi saldo está mal, quiero hablar con una persona" hands over with a case reference and a due time |
| Cards | `crd-mx-two-cards` | "Perdí mi tarjeta, bloquéala por favor" asks which card; "la primera" shows a confirmation card (card, action, reason) with Confirm and Cancel; Confirm opens the "Confirm it is you" dialog with a new demo code; after it the reply says the block is done and the action shows "Verificado" (the conversation's language), with the product id it was checked against |
| Cards | `crd-co-declined`, `crd-mx-blocked` | Card status asks which card, then answers; an unblock request goes to a person (no unblock tool exists) |
| Disputes | `dsp-co-unrecognized` | Ask for the April statement of the credit card, pick the first card, then write "No reconozco el cargo de [merchant] del [date] por [amount]" copying one purchase line from the statement table (not the cash withdrawal). The assistant asks to leave the statement question ("Sí"), offers a protective block ("No, gracias"), shows the claim with its deadline, and registers the case only after Confirm and the step-up code |
| Disputes | `dsp-mx-open-case`, `dsp-co-unrecognized` | Case status answers with the case id and its committed date (45 days after the seed); a complaint to the regulator hands over at once |
| Credit | `cre-mx-complete`, `cre-co-no-income`, `cre-ar-borderline`, `cre-co-application` | Catalog answers; "Orientación de elegibilidad, Servicio sintético" cards with reasons, rules, and uncertainty, never approval wording and never a score; "Apruébame el crédito ya" abstains; the review button hands over; the seeded application answers with its status |

A charge can be disputed once and a card blocked once per database, so a second pass needs a [reset](#5-reset-the-demo-data).

**Agent console** (`agent-demo-01`, `/console`). Inbox: a table of handoffs with filters for status, workflow, priority, reason, language, and due time; each row is a structured summary, never a transcript. Filter Workflow = Credit, open a handoff: request, verified facts with sources, actions taken, policy basis with clause text, open questions, and the credit review with the internal estimate the customer never saw. "Claim handoff" opens a confirmation; after it, "Resolve" asks for an outcome (resolved by the agent, case updated, referred, no action, unreachable, other) and a note, and the status becomes Resolved. Credit applications: the seeded `app-seed-...` application, whose page offers "Take into review".

**Evaluator console** (`evaluator-demo-01`). Records (`/console/traces`): paste a conversation reference; the record shows every turn plus, for credit, separate "Risk estimate" and "Eligibility decision" panels and an "Evaluation only" section. Evaluation (`/console/evaluation`): the published run `test-local` (commit `6bc2e9d`, 332 test scenarios), one table per workflow for B0, B1, and P with sample sizes and 95% intervals, then the aggregate (P 177/304), the language slices, and the labels (simulated; projected where priced).

**Public pages.** `/about` states what each workflow does and does not do, and that the data and the credit rules are synthetic. `/demo` is the guide above. Both work without signing in.

**Themes, languages, mobile.** The Preferences sheet offers Español (México, Colombia, Argentina), Português (Brasil), and English, and the theme (system, light, dark). A conversation reads in its own language whatever the interface language is. At 390 px wide the record moves behind a "Record" button (a dialog) and no page scrolls sideways.

## 3. The fake model and the local Ollama model

`.env` from `make env` sets `LLM_PROVIDER=fake`: no model is called, every workflow takes its deterministic path, and the record says so per prompt. To use the local model, keep `.env` as it is and pass the three settings on the command line.

```bash
ollama list                                   # qwen2.5:7b-instruct must be listed
LLM_PROVIDER=litellm LLM_PRIMARY_MODEL=ollama/qwen2.5:7b-instruct LLM_API_BASE=http://localhost:11434 make llm-smoke
make api-local-llm                            # instead of the uvicorn command above; the web dev server stays as it is
```

A bare `make llm-smoke` reads the fake provider from `.env` and stops with `llm-smoke: set LLM_PROVIDER=litellm and LLM_PRIMARY_MODEL ...` (exit 2). With the three settings it runs the 32 fixture cases (four workflows, es and pt): 32 of 32 passed in 2 min 24 s, p50 4.0 s and p95 7.5 s per call; the first call takes about 17 s while Ollama loads the model. `make api-local-llm` sets the same three values itself; `/health/details` then shows `llm_primary: ok`. It runs without `--reload`; stop it with Ctrl-C.

With the local model all 16 demo-guide scenarios completed in Spanish and in Portuguese through the browser. Per turn: p50 4.8 s, p95 7.7 s, at most 8.2 s (47 turns), against about 0.7 s with the fake provider. The record now lists each model call (`detect_escalation_signals@1`, `extract_<workflow>_slots@1`) with its tokens and latency, at a cost of $0.00. Differences seen against the fake provider:

- In both Spanish runs (dev stack and production stack), "Perdí mi tarjeta, bloquéala por favor" from `crd-mx-two-cards` went straight to the confirmation for the credit card instead of asking which card, so the guide's next message ("la primera") got "No te entendí. Responde sí para confirmar o no para cancelar"; press Confirm (or Cancel) on the card shown instead. The confirmation names the card before anything is written. The Portuguese run on the same model asked which card. Recorded in [BACKLOG](../BACKLOG.md).
- Every scenario ended in the same final state and outcome as with the fake provider; the card choice above was the only difference in the path.

## 4. Evaluation: the smoke suite and the published report

```bash
make eval-smoke          # 1.4 s: b0 5/12, p 8/12, b1 0/12 safe automated resolution, 0 unsafe; writes reports/eval/smoke/
```

`make eval-test` replays the frozen test split from the committed cassettes without a model in about 13 s (1,284 cases). It is a deterministic regression run, not the published numbers: it misses 214 cassettes and gives B0 116/304, P 165/304 (4 unsafe), B1 39/304 (90 unsafe), against the published 128, 177 (8 unsafe), and 39 (90 unsafe). The same happens at the run's own commit `6bc2e9d`: when the live run recorded two calls with identical inputs (each system's first simulated-customer turn of a scenario, and the repeated runs), the second overwrote the first, so the replay diverges from there ([methodology](../evaluation/methodology.md)).

The published documents are regenerated from the run directory, which is not in git because `results.jsonl` holds the transcripts (it is on the technical lead's machine, in the `eval-run` worktree). With a copy at `reports/eval/test-local`:

```bash
uv run --frozen bank-eval publish reports/eval/test-local --title "Evaluation results: session 14b test run (test split, local model qwen2.5:7b-instruct)"
git diff --stat          # only the hand-written analysis sections of results.md and failures.md are gone
git checkout -- docs/evaluation/results.md docs/evaluation/failures.md
```

It takes under a second and needs no model. In the verification run the summaries (`evals/reports/summaries/test-local-*.json`), `docs/evaluation/runs/test-local/`, and the generated part of `results.md` and `failures.md` came out byte for byte as committed; only the two hand-written sections were dropped, as documented.

## 5. Reset the demo data

Writes persist: a blocked card, an opened case, a handoff, an intake. `make seed` restores card statuses but keeps cases and intakes, so a clean demo needs a fresh volume. Stop the API first or let it reconnect.

```bash
make down
docker volume rm bank-agent_pgdata         # or <COMPOSE_PROJECT_NAME>_pgdata; erases the local database
make up
make seed                                  # migrates, then loads; about 9 s for the whole reset
```

Do not use `docker compose down --volumes` on a checkout whose data you want to keep; it removes every volume of that project.

## 6. The production stack on this machine (local TLS mode)

The same stack a VM runs (Caddy with its own certificate authority, two API workers, PostgreSQL with a non-superuser owner, the migrate, seed, and purge jobs), with the local Ollama model. It publishes only 8080 and 8443, so it runs beside the dev stack. Caddy binds them on every interface (`0.0.0.0`), so other machines on the network can reach the demo while it runs. Keep the env file outside the repository.

```bash
export ENV_FILE=$HOME/bank-agent-local.env PROJECT=bank-agent-local
deploy/prod.sh init-env        # under 1 s: fresh secrets, mode 600
```

Then set these lines in that file (a text editor is fine; never paste the secrets anywhere):

```text
SITE_ADDRESS=localhost
PUBLIC_ORIGIN=https://localhost:8443
CADDY_TLS=internal
HTTP_PORT=8080
HTTPS_PORT=8443
DEMO_MODE=true
ALLOW_PUBLIC_DEMO_MODE=true
VITE_DEMO_MODE=true
LLM_PROVIDER=litellm
LLM_PRIMARY_MODEL=ollama/qwen2.5:7b-instruct
LLM_API_BASE=http://host.docker.internal:11434
LLM_ALLOW_PRIVATE_HTTP_BASE=true
LLM_TIMEOUT_SECONDS=60
```

(`LLM_PROVIDER=fake` instead of the five `LLM_` lines runs it without a model.)

| Step | Command | Time | What you should see |
|---|---|---|---|
| Validate | `deploy/prod.sh check` | under 1 s | `env file and compose file are valid` |
| Images | `deploy/prod.sh build` | 1 min 52 s warm | `built images tagged <12-character commit>` (web, api, job) |
| Start | `deploy/prod.sh up` | 20 s | postgres, api, web healthy, `migrate` exited, then `running image tag <commit>` |
| Seed | `deploy/prod.sh seed` | 4 s | The same counts as the dev seed |
| Root certificate | `docker cp bank-agent-local-web-1:/data/caddy/pki/authorities/local/root.crt /tmp/caddy-root.crt` | under 1 s | The local CA, for the smoke test |
| Smoke | `make smoke SMOKE_URL=https://localhost:8443 SMOKE_ARGS="--ca-file /tmp/caddy-root.crt --min-cert-days 0"` | 1 to 2 min | `ok` lines for TLS, health, headers, the demo sign-in and cookies, a conversation per workflow in es and pt through the model, an abstention, and a cross-customer 404, then `smoke test passed` |
| CSP | `make csp-check SMOKE_URL=https://localhost:8443 CSP_ARGS=--ignore-https-errors` | 5 to 6 min | Several `sign-in ... (rate limit), retrying in 30 s` lines (expected: the production limits apply), then `csp check passed: no CSP violation, console error, or failed request over 45 page loads` |

`/health/details` at `https://localhost:8443/health/details` shows `llm_primary: ok`. The browser warns about the certificate (Caddy's local authority); accept it for `https://localhost:8443`, then use the app exactly as in section 2. `make smoke` without `SMOKE_ARGS` fails with `CERTIFICATE_VERIFY_FAILED`, and `make csp-check` without `CSP_ARGS` fails on the certificate too.

Take it down and remove its data, images aside:

```bash
docker compose -f deploy/compose.prod.yml --env-file "$ENV_FILE" -p "$PROJECT" --profile '*' down --volumes
rm "$ENV_FILE" /tmp/caddy-root.crt
docker image rm bank-agent-api:<tag> bank-agent-job:<tag> bank-agent-web:<tag>   # optional, about 2.1 GB
```

## 7. The slides

```bash
cd slides
pnpm install             # 5 s warm
pnpm verify              # 4 s: types, then check:content; ends "ok content is consistent, 1 metric(s) pending"
pnpm dev                 # http://localhost:3131 (presenter view at /#/presenter); leave it running
pnpm check:fit           # second terminal, 2 s: "ok every scene fits the safe area at every cue, with no overlapping text"
pnpm export              # draft PDF, 4 s warm: export/la-brasil-del-70-pitch.pdf (35 pages, gitignored)
```

The pending metric is `deploy.url`, filled after the deployment; until then `pnpm export:final` stops on purpose. The export prints a `Failed to patch FloatingVue` console error from Slidev's own client; it does not affect the PDF. `pnpm export` launches its own server, so it does not need `pnpm dev`.

## 8. The gates

```bash
make check               # every gate; needs Docker, never reads .env
make submission-check    # make check, make security, make eval-smoke, the slides verify, make docs-check, then the human steps
```

Measured: `make check` 8 min 12 s, `make submission-check` 7 min 56 s (it runs `make check` again, then `make security`, `make eval-smoke`, the slides' verify, and `make docs-check`, printing `pass` per gate and then the human steps that remain). `make check` starts its own PostgreSQL containers through testcontainers, so it does not need `make up` and does not touch the dev database. `make security` needs the network (pip-audit and `pnpm audit`) and pulls pinned tool images on first use.

## Troubleshooting

Every row is a friction point met during the verification run. Rows marked "fixed" were corrected on the verification branch; the others describe what to do.

| Symptom | Cause and fix |
|---|---|
| `make setup` stops at `pnpm install` with `ERR_PNPM_UNSUPPORTED_ENGINE ... Expected version: >=24.15.0 <25, Got: v24.14.1` | nvm's default Node is older than 24.15. Run `nvm use 24` (or `nvm install 24` first) in that shell |
| A second checkout's `make up` recreates `bank-agent-postgres-1`, then `make db-upgrade` fails to sign in | Both checkouts use the compose project `bank-agent`. Export `COMPOSE_PROJECT_NAME` and `POSTGRES_PORT` in the second checkout ([above](#a-second-checkout-on-the-same-machine)); documented now in `.env.example` and AGENTS.md |
| `curl localhost:8000/healthz` gives 404 | The health routes are `/health/live`, `/health/ready`, and `/health/details` |
| "Too many requests in a row" at sign-in | The auth limit: 10 requests per minute per address, three per sign-in. Wait a minute, or start the API with `RATE_LIMIT_AUTH_PER_MINUTE=200 RATE_LIMIT_SESSION_AUTH_PER_MINUTE=200` (and the `WRITE` pair for fast scripted conversations); development only |
| A Spanish credit question gets "¿En qué idioma prefieres que te atienda: español o portugués?" | The session takes the interface language; from an English browser that is `en`, and a message with few Spanish words cannot be placed. Answer "español", or write a clearly Spanish sentence. Fixed for the demo guide: its three credit messages were rephrased, and a test checks every first message |
| The dispute intake asks again for "la fecha aproximada, el monto y el comercio" after "Sí" | Before the fix the parser did not read the date and amount the statement table shows ("23 abr 2026", "23 de abr. de 2026", "COP 1,015,801.59"); only a Colombian-Spanish browser (`23/04/2026`) worked. Fixed: abbreviated dates and currency codes before the amount are read |
| "No puedo registrar esta reclamación aquí" when disputing the same charge again | A charge can be disputed once per database; [reset](#5-reset-the-demo-data) |
| The balance card says "Datos al 18 jun 2026, 12:59 a.m." while the reply says "17 de junio" | The card shows the data cut (`2026-06-18T05:59:59Z`, the end of 17 June in Mexico City) in the browser's time zone. Not changed: which zone to show is a human decision ([BACKLOG](../BACKLOG.md)) |
| "Assistant" in English beside the avatar in a Spanish or Portuguese chat | The API's default assistant name in the secondary assistant-profile feature; localization remains a low-priority follow-up ([BACKLOG](../BACKLOG.md)) |
| A card shows "Activa" with an expiry date in 2023 (`crd-co-declined`) | The organizer's synthetic data; the assistant reports what the record says |
| The evaluation view repeated its run notes three times, and the console showed React duplicate-key errors | Fixed: each note shows once, and a note only some systems carry names them |
| `make llm-smoke` exits 2: `set LLM_PROVIDER=litellm and LLM_PRIMARY_MODEL` | `.env` keeps the fake provider; pass the three settings on the command line ([section 3](#3-the-fake-model-and-the-local-ollama-model)); README and AGENTS.md now say so |
| `make eval-test` reports `cassette misses 214` and numbers that differ from the published ones | Expected; a replay is not the recorded run ([section 4](#4-evaluation-the-smoke-suite-and-the-published-report)) |
| `--llm replay needs LLM_PRIMARY_MODEL` when calling `bank-eval run` directly | `make eval-test` sets it; by hand add `LLM_PRIMARY_MODEL=ollama/qwen2.5:7b-instruct` |
| `make smoke` against the local stack: `CERTIFICATE_VERIFY_FAILED` | Caddy's local authority is not trusted; pass `SMOKE_ARGS="--ca-file /tmp/caddy-root.crt --min-cert-days 0"`. Fixed: the target did not accept the flags before |
| `make csp-check` against the local stack fails on the certificate, or times out waiting for a table | Pass `CSP_ARGS=--ignore-https-errors`. The timeout was the empty agent inbox of a fresh seed; fixed |
| `make csp-check`: `Executable doesn't exist at .../ms-playwright/chromium-...` | pnpm does not download the browser: `pnpm --dir apps/web exec playwright install chromium`, once |
| `make csp-check` prints `retrying in 30 s` several times and takes almost 6 minutes | The production auth limit applies to its sign-ins; expected |
| The production stack is reachable from other machines | Caddy publishes 8080 and 8443 on every interface; take the stack down when you are done |
| `pnpm dev` in `slides/` and another Slidev deck | This deck uses port 3131, so it does not clash with a deck on Slidev's default 3030 |
| `pnpm export` prints `Failed to patch FloatingVue` | Noise from Slidev's client; the PDF is complete |
| `pnpm export:final` stops on a pending metric | By design until `deploy.url` is filled in `slides/data/metrics.yml` after the deployment |

## Verification log

Date: 2026-09-30. Started from `main` at `b1e1f7b` in a fresh clone, on the branch `e2e-verify`; the fixes below are commits on that branch. Machine: the one in [Prerequisites](#prerequisites), with the main checkout's dev PostgreSQL running on 5432 the whole time (the clone used `COMPOSE_PROJECT_NAME=bank-agent-e2e` and port 5442).

| # | Check | Result | Notes |
|---|---|---|---|
| 1 | Development path with the committed sample: `make env`, `setup`, `up`, `db-upgrade`, `pipeline`, `seed`, `env-check`, the API and the web dev server | Pass | 3 min 20 s from the clone to both servers answering, with warm caches |
| 2 | Browser walkthrough (Playwright, fake model): 16 demo-guide scenarios in es (English browser) and 16 in pt (Portuguese browser), step-up dialog, glass box and its route, agent inbox, handoff claim and resolve, credit applications, evaluator record and evaluation view, about, demo guide, preferences, dark theme, 390 px width | Pass after fixes | Failed first on the dispute intake (dates and amounts from the statement) and on three Spanish credit messages from an English browser, and logged React key errors in the evaluation view; all three fixed. No console error and no failed request afterwards |
| 3 | Local model: `make llm-smoke` (with the three settings), `make api-local-llm`, all 32 guide conversations through the browser | Pass | llm-smoke 32 of 32 in 2 min 24 s; per turn p50 4.8 s, p95 7.7 s; one behavior difference (the card choice in Spanish), recorded in BACKLOG |
| 4 | Evaluation: `make eval-smoke`; regenerate the published report without a model | Pass for `eval-smoke` and for `bank-eval publish` on the run directory (byte for byte); the committed cassettes alone cannot reproduce the published numbers | Replay: 214 misses, P 165/304 against 177/304, the same at `6bc2e9d`; documented in the methodology, a harness fix is in BACKLOG for a human decision |
| 5 | Local production stack: `init-env`, `check`, `build`, `up`, `seed`, `make smoke`, `make csp-check`, two write flows in the browser through the model, then down with its volumes | Pass after fixes | `make smoke` and `make csp-check` could not take the local CA flags, and the CSP check timed out on a fresh seed's empty inbox; both fixed |
| 6 | Slides: `pnpm install`, `pnpm verify`, `pnpm dev`, `pnpm check:fit`, draft `pnpm export` | Pass | 35-page PDF; 1 metric pending (`deploy.url`) by design |
| 7 | `make check` and `make submission-check` in the clone | Pass | At `dd03fba`: `make check` 8 min 12 s (2,870 unit, 1,489 integration with 3 skipped for the optional `ml` extra, 349 web tests, all 11 coverage gates); `make submission-check` 7 min 56 s, every gate `pass`, then the seven human steps |

Commits on `e2e-verify`:

| Commit | Change |
|---|---|
| `3332627` | fix(workflow): read the dates and amounts the statement table shows |
| `b166312` | fix(web): open every demo-guide conversation in a detectable language |
| `44e3f6d` | fix(web): list each evaluation run note once and name its systems |
| `5cb8526` | docs(evals): state that a cassette replay does not reproduce the run |
| `dc4fd1b` | docs(docs): record the local end-to-end findings that need a decision |
| `7c5d2a4` | fix(infra): let the CSP check pass on a freshly seeded stack |
| `c018f25` | fix(infra): pass the local CA flags through make smoke and csp-check |

Needs a human decision (each has a BACKLOG row): re-recording the evaluation cassettes so a replay reproduces a run; the time zone of the as-of instant in the answer cards; the model choosing a card the customer did not name. The English default assistant name is an accepted low-priority localization follow-up for the secondary assistant-profile feature. Also for the human: `slides/package.json` declares `"license": "Apache-2.0"` while the repository states "All rights reserved; no license is granted".
