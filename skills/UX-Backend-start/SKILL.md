---
name: UX-Backend-start
description: Start the whole local product (PostgreSQL, the API, and the web UX) from whatever state the machine is in, then open it in the browser. It inspects first, runs only the missing steps (Docker, configuration, data pipeline, seed, migrations, containers), and delegates to the setup-postgres-data, download-organizer-data, and github-collaboration skills when their conditions apply. Use it when someone asks to start, run, open, or set up the app, the UX, the UI, the frontend, or the backend.
---

# Start the UX and the backend

The goal is a working product at `http://localhost:5173`: PostgreSQL seeded with demo data, the API healthy on `:8000`, and the web app served by Vite, opened in the browser. Run from the repository root. Every step is idempotent: inspect, skip what is already done, and do only what is missing.

Two entry points exist:

| Entry point | Who uses it | What it does |
|---|---|---|
| This skill | An agent | The full flow: first-time setup, repair, data, seed, start, verify, open |
| `skills/UX-start.bat` | A person on Windows (double-click) | The daily start once setup is done: Docker, containers, health checks, browser. `stop`, `status`, `--no-browser`, and a server URL are also supported |

## Guardrails

- Never read, print, or copy `.env`. Check variables with `scripts/checks/check_env_keys.py`, which reports only set or unset.
- Never run `docker compose down --volumes`, delete a volume, or reset the database without the human's explicit approval: it erases the local data.
- Never download the organizer dataset on your own initiative. Follow `download-organizer-data`: only on request, with credentials the human supplies for that run.
- Never commit, push, or change branches. Report the git state instead.
- Install project dependencies freely (images, the Python environment, `node_modules`: they install inside containers). Ask before installing system software (Docker Desktop, WSL, Python, uv).

## How the other skills fit

This skill is the entry point; the others run inside it when their conditions hold, never unconditionally.

| Skill | When it runs in this flow | What it owns |
|---|---|---|
| [setup-postgres-data](../setup-postgres-data/SKILL.md) | Steps 4, 6, and 7, whenever the database volume is new, empty, or behind on migrations | PostgreSQL start and init checks, the data source choice, pipeline from the sample, seed, verification |
| [download-organizer-data](../download-organizer-data/SKILL.md) | Step 6, only when the human asks for the full organizer data and no full warehouse exists | The S3 download with credentials supplied for that run |
| [github-collaboration](../github-collaboration/SKILL.md) | Never during a start. Only when the human then asks for a pull request, issue, or review | GitHub operations through `gh` |

Read each delegated skill before running its part. Where this file adds a Docker variant of a command (step 2), the delegated skill's rules still apply.

## Step 0: inspect and announce the plan

Run these read-only checks in one pass, then tell the human which steps will run and which are already done, and continue without waiting unless a step needs them.

| Check | Command | Meaning |
|---|---|---|
| Git state | `git status --short --branch` | Report the branch and whether it is behind its upstream. If the tree is clean and behind, offer `git pull --ff-only`; do not pull unasked |
| Docker CLI and engine | `docker version --format "{{.Server.Version}}"` | No output or an error: go to step 1 |
| Stack state | `docker compose --profile '*' ps -a --format "{{.Service}} {{.Status}}"` | Which containers exist and whether they are healthy |
| Database volume | `docker volume ls --format "{{.Name}}"` | `bank-agent_pgdata` present means the passwords in `.env` are already fixed |
| Configuration | `test -f .env`, `test -f apps/web/.env.local` | Presence only, never contents |
| Gold data | `ls data/warehouse/gold data/warehouse-sample/gold` | Which source can be seeded without rebuilding |
| Full download | `ls data/warehouse/raw data/warehouse/manifest.duckdb` | A previous S3 download that has not been built yet |
| Platform | `uname -s` (`MINGW`, `MSYS`, or `CYGWIN` means Windows) | Chooses the Python runtime in step 2 |

Fast path: if the three containers exist, `.env` exists, and the database probe in step 7 finds customers, jump to step 8.

## Step 1: Docker engine

1. If the engine is not answering, start Docker Desktop and poll `docker version` every few seconds, for up to three minutes:
   - Windows: `"/c/Program Files/Docker/Docker/Docker Desktop.exe" &` from Git Bash, or `start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"` from cmd.
   - macOS: `open -a Docker`.
   - Linux: ask the human to start the Docker service.
2. Confirm with `docker run --rm hello-world`.
3. If Docker Desktop reports "Virtualization support not detected", the hypervisor or WSL 2 is missing (see Troubleshooting). That needs an administrator and a reboot: explain it and stop.

## Step 2: choose the Python runtime

The data and database commands (`bank-data`, `bank-agent`) run either on the host with `uv` or in a disposable toolbox container.

- macOS and Linux: use the host, `uv run --frozen <command>`.
- Windows: use the toolbox container by default. Windows Smart App Control blocks the unsigned native files that the Python dependencies ship (`_ssl`, DuckDB, the `bank-data.exe` launcher), and the toolbox avoids it entirely. Use the host only if the human asks and `uv run --frozen python -c "import ssl, duckdb"` succeeds.

Toolbox definition. Shell state does not persist between tool calls, so define it in the same command that uses it. Keep the image tag equal to the one in `services/api/Dockerfile.dev`:

```bash
REPO_DIR="$(pwd -W 2>/dev/null || pwd)"
toolbox() {
  MSYS_NO_PATHCONV=1 docker run --rm $TOOLBOX_NETWORK \
    -v "$REPO_DIR:/workspace" -w /workspace \
    -v bank-data-venv:/opt/venv -v bank-data-uv-cache:/opt/uv-cache \
    -e UV_PROJECT_ENVIRONMENT=/opt/venv -e UV_CACHE_DIR=/opt/uv-cache \
    -e UV_PYTHON_DOWNLOADS=never -e UV_LINK_MODE=copy \
    -e POSTGRES_HOST=postgres -e POSTGRES_PORT=5432 \
    ghcr.io/astral-sh/uv:0.11.17-python3.12-trixie-slim uv run --frozen "$@"
}
TOOLBOX_NETWORK="--network bank-agent_default"   # leave empty before PostgreSQL has started
toolbox --package bank-data bank-data --help
```

- `MSYS_NO_PATHCONV=1` and `pwd -W` stop Git Bash from rewriting the container paths.
- The two named volumes keep the environment and the download cache between runs. The first run installs about 160 packages; later runs start in seconds.
- `.env` is read by the programs inside the container from the mounted repository. You never pass its values yourself.
- The network name comes from the Compose project name (`name: bank-agent` in `docker-compose.yml`). With it, the toolbox reaches PostgreSQL as `postgres:5432`.

## Step 3: configuration and line endings

1. `.env`:
   - Present: keep it. Run `toolbox --no-project python scripts/checks/check_env_keys.py` on Windows, or `uv run --no-project --python 3.12 python scripts/checks/check_env_keys.py` elsewhere, and confirm the required variables are set.
   - Absent, and `bank-agent_pgdata` absent: create it with fresh development secrets. Use `python scripts/make_env.py` (standard library only, so a host Python works, including on Windows), or `make env`.
   - Absent, but `bank-agent_pgdata` present: stop and ask. A new `.env` would not match the passwords the volume was created with. The options are the human restoring their old `.env`, or approving a volume reset.
2. `apps/web/.env.local`: if absent, write `VITE_DEMO_MODE=true` to it. It enables the demo persona picker on the sign-in page, is gitignored (check with `git check-ignore -q apps/web/.env.local`), and holds no secret.
3. Shell scripts must have LF endings before PostgreSQL first initializes its volume, or `deploy/postgres/init/10-roles.sh` fails with `bad interpreter`. On Windows, detect with Python (Git Bash `grep` hides carriage returns). If any tracked `*.sh` has CRLF and the tree has no changes to it, delete and restore it (`rm <file> && git checkout -- <file>`) so `.gitattributes` applies LF.

## Step 4: PostgreSQL

Follow `setup-postgres-data`, "Create the database and load it":

1. `docker compose up -d --wait postgres`, then `docker compose ps postgres` must say `healthy`.
2. On a volume created in this run, `docker compose logs --no-color postgres` must show `CREATE ROLE` and `CREATE SCHEMA` and no init error. A healthy server alone is not enough.
3. Save time: start `docker compose --profile api --profile web build` in the background now. The images build while the data steps run.

## Step 5: migrations

Run `toolbox --package bank-agent bank-agent db upgrade` (with `TOOLBOX_NETWORK` set). It is idempotent, prints the schema revision, and brings an existing database up to date after a pull. The seed in step 7 also migrates, so this step only matters when step 7 is skipped.

## Step 6: data source

Choose the first row that matches, following `setup-postgres-data`, "Select the data source":

| Evidence | Action | Source for step 7 |
|---|---|---|
| `data/warehouse/gold/customers_serving.parquet` exists | Nothing to build | `s3` |
| `data/warehouse/raw/` and `data/warehouse/manifest.duckdb` exist, no gold | Build the full data: `bank-data ingest --source s3`, then `build`, then `test` | `s3` |
| `data/warehouse-sample/gold/customers_serving.parquet` exists | Nothing to build | `sample` |
| None of these, and the human asked for the full organizer data | Run `download-organizer-data`, then build as in the second row | `s3` |
| None of these | Build the committed sample offline: `ingest`, `build`, `test` with `--source sample` | `sample` |

- The `s3` ingest lists the bucket again, so it needs the organizer variables set in `.env` (check with `check_env_keys.py`). If they are missing, tell the human and fall back to the sample.
- Durations: the sample builds in under a minute. The full delivery took about 45 minutes on Windows through the toolbox, because the container reads and writes thousands of files on a Windows disk. Run it in the background and report progress from the size of `data/warehouse/bronze` and the number of its files.
- Expected quarantine: about 24,029 `call_transcripts` rows without a duration (a known data issue). It is not a failure.

## Step 7: seed

Probe first. This needs no password, because the database container trusts its own local socket:

```bash
docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select count(*) from app.customers"'
```

- A positive number: the database is already seeded. Skip the seed. Seeding again restores blocked cards but keeps opened cases and intakes, so reseed only when the human asks, for example before recording a demo.
- `0` or an error: run `toolbox --package bank-data bank-data seed --source <source> --customers 200`, with `TOOLBOX_NETWORK` set and the source from step 6. Report the counts it prints. With the full data they were 200 customers, 2 staff members, 200 identity entries, 559 products, 6,119 transactions, 84 historical complaints, 200 credit profiles, 1 dispute case, and 1 credit application.

## Step 8: API and web app

`docker compose --profile api --profile web up -d --wait`

- It builds the images if they are missing. On start, the containers install their own dependencies: `uv` syncs the API environment and `pnpm install --frozen-lockfile` runs for the web app. New dependencies after a pull need no extra step.
- The API reads `.env` (`DEMO_MODE=true` shows one-time codes on screen). The web app proxies `/api` and `/health` to the API.

## Step 9: verify

All of these must hold before you report success:

| Check | Expected |
|---|---|
| `curl -s localhost:8000/health/ready` | `"status":"ready"` with `"database":"ok"` |
| `curl -s -o /dev/null -w "%{http_code}" localhost:5173/` | `200` |
| `curl -s -o /dev/null -w "%{http_code}" localhost:5173/health/live` | `200` (the web-to-API proxy works) |
| `docker compose logs --no-color api` | No `error` entries after `Application startup complete` |
| Sign-in page (browser tool, if available) | "Ingresa a tu banca" with the demo persona list |
| `git status --short` | No new tracked changes; `.env`, `apps/web/.env.local`, and `data/` stay ignored |

## Step 10: open and report

1. Open `http://localhost:5173`: `start "" http://localhost:5173` on Windows, `open` on macOS, `xdg-open` on Linux. On Windows `skills/UX-start.bat` does steps 8 to 10 in one command.
2. Report in a short table: each step (done, skipped, or blocked), the data source, the seed counts or the probe count, and the URLs.
3. Give the sign-in hint: pick a persona on the sign-in page (for example `acc-mx-accounts`, `crd-mx-two-cards`, `agent-demo-01`, or `evaluator-demo-01`). The one-time code appears on screen. With `LLM_PROVIDER=fake`, answers come from deterministic templates by design.
4. Give the stop command: `docker compose --profile '*' down`, or `skills/UX-start.bat stop`. The database survives in its volume.

## Deployed server

A deployment to a server is not part of this skill; production deployment is described in `deploy/README.md`. When a deployed URL exists, open it directly, or run `skills/UX-start.bat https://<host>`.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Docker Desktop: "Virtualization support not detected" | Hardware virtualization is usually on in the firmware, but Windows has no hypervisor or WSL 2. An administrator runs `wsl --install` and reboots. If it persists, run `bcdedit /set hypervisorlaunchtype auto` and reboot again |
| `DLL load failed ... Una directiva de Control de aplicaciones bloqueó este archivo` (or "An Application Control policy has blocked this file") | Windows Smart App Control. Use the toolbox (step 2). Do not suggest turning Smart App Control off: it lowers the machine's protection, and on many Windows builds it cannot be turned back on without a reset. Check its state with `reg.exe query "HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy" /v VerifiedAndReputablePolicyState` (1 means on) |
| `Failed to spawn: bank-data` with os error 4551 | Same cause, for the `.exe` launcher. Use the toolbox |
| PostgreSQL logs `/bin/sh^M: bad interpreter`, or no `CREATE ROLE` | CRLF in `10-roles.sh` when the volume was created. Fix the line endings (step 3), then ask the human before recreating the volume |
| Password authentication fails for `bank_app` or `bank_owner` | `.env` does not match the volume. Compare variable names only; never print values. Ask before any volume reset |
| `port is already allocated` for 5432, 8000, or 5173 | Another process holds the port. Find it (`netstat -ano` on Windows, `lsof -i` elsewhere) and ask the human before stopping it |
| `--wait` reports a container as unhealthy | Read `docker compose logs --no-color --tail 80 <service>`, fix the cause, run step 8 again |
| The seed says no gold tables exist | Go back to step 6 and build the matching source |
| The sign-in page shows no persona list | `apps/web/.env.local` is missing or the web container started before it existed. Write it, then `docker compose --profile web up -d --force-recreate web` |
| The API fails after a `git pull` with a missing column or table | Run step 5 (migrations) |
