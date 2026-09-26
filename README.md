# factored-hackathon-2026-la-brasil-del-70

An AI-first banking customer-service system for the Factored AI & Data Hackathon 2026. The chosen workflow is transaction-dispute intake and dispute status, with a protective card block as a sub-action, in Spanish and Portuguese.

Design thesis: the language model understands, deterministic code decides, and evidence proves it. Permissions and policy are enforced in code, identity comes from a trusted session, and the system reports only outcomes it has verified.

Status: under construction. Phase 01 (monorepo scaffold and quality gates) is complete; the domain, data platform, policy, workflows, and user interface arrive in later phases. Progress is tracked in [docs/PROGRESS.md](docs/PROGRESS.md).

## Repository map

| Path | Content |
|---|---|
| [`services/api`](services/api/README.md) | `bank-agent`: FastAPI service with a hexagonal core (domain, ports, policy, application, adapters, api, bootstrap) |
| [`apps/web`](apps/web/README.md) | Vite, React 19, and TypeScript client with layered folders (app, pages, features, entities, shared) |
| [`data_platform`](data_platform/README.md) | `bank-data`: ingestion, contracts, dbt-duckdb transformations, data reports |
| [`ml`](ml/README.md) | `bank-ml`: intent router and transaction resolver training |
| [`evals`](evals/README.md) | `bank-evals`: evaluation harness comparing baselines and the proposed system |
| [`deploy`](deploy/README.md) | PostgreSQL role bootstrap and observability configuration; production deployment later |
| [`docs`](docs/README.md) | Architecture, ADRs, plans, progress, and organizer material |
| `scripts` | Repository checks and git hooks |
| `data/` | Gitignored: raw data, warehouse, artifacts |

The working agreement for contributors, human or automated, is [CLAUDE.md](CLAUDE.md). The organizer brief and dataset schema are in [docs/organizer](docs/organizer/).

## Prerequisites

- [uv](https://docs.astral.sh/uv/) 0.11.17 or later (it installs Python 3.12 from `.python-version`)
- Node.js 24.15 or later (see `.nvmrc`) with pnpm 10.33 (pinned by `apps/web/package.json`)
- Docker with Compose v2 or later (PostgreSQL for integration tests and the dev stack)
- [pre-commit](https://pre-commit.com/) and [gitleaks](https://github.com/gitleaks/gitleaks)

## Quickstart

```bash
make setup     # Python and web dependencies, git hooks
make check     # every quality gate; needs Docker, never needs .env
```

To run the development stack, create `.env` from `.env.example` and fill in the values locally (never commit it or paste it anywhere), then:

```bash
make up                       # PostgreSQL
make up PROFILES="api web"    # plus the API on :8000 and the web app on :5173
make down
```

`make help` lists every target. `make env-check` reports which documented variables are set without printing any value.

## Documentation

Start at the [documentation index](docs/README.md). Key entries: the [architecture overview](docs/architecture/overview.md), the [architecture decision records](docs/adr/README.md), [CONTRIBUTING.md](CONTRIBUTING.md), and [SECURITY.md](SECURITY.md).

## License

No license has been chosen yet. Until one is added, all rights are reserved by the authors.
