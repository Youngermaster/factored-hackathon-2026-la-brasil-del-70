# factored-hackathon-2026-la-brasil-del-70

An AI-first banking customer-service system for the Factored AI & Data Hackathon 2026. It covers four workflows, each built in depth: account and payment inquiries, card support (including a protective card block), transaction-dispute intake and status, and credit-product information with an indicative, synthetic eligibility service, in Spanish and Portuguese.

Design thesis: the language model understands, deterministic code decides, and evidence proves it. Permissions and policy are enforced in code, identity comes from a trusted session, and the system reports only outcomes it has verified.

Status: under construction. The scaffold, the domain model and contracts, the LLM gateway, and the data platform are in place; policy, workflows, and the user interface arrive in later phases. Progress is tracked in [docs/PROGRESS.md](docs/PROGRESS.md).

## Repository map

| Path | Content |
|---|---|
| [`services/api`](services/api/README.md) | `bank-agent`: FastAPI service with a hexagonal core (domain, ports, policy, application, adapters, api, bootstrap) |
| [`apps/web`](apps/web/README.md) | Vite, React 19, and TypeScript client with layered folders (app, pages, features, entities, shared) |
| [`data_platform`](data_platform/README.md) | `bank-data`: ingestion, contracts, dbt-duckdb transformations, data reports |
| [`ml`](ml/README.md) | `bank-ml`: intent router, transaction resolver, and credit risk estimator training |
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

To run the development stack, create `.env` first. Both ways give a working local environment with no edits (never commit `.env` or paste it anywhere):

```bash
make env                      # the stronger option: copies .env.example and generates fresh random dev secrets
cp .env.example .env          # also works: the example's dev-only secrets are refused in production
```

Then:

```bash
make up                       # PostgreSQL
make up PROFILES="api web"    # plus the API on :8000 and the web app on :5173
make down
```

The organizer S3 values stay empty unless you need the full delivery (`make data-download` with `DATA_SOURCE=s3`); the team takes them from the organizer data dictionary, which is never committed. `make help` lists every target. `make env-check` reports which variables the current configuration needs and whether each is set, without printing any value. An opt-in local language model (Ollama) is described in `.env.example` and [docs/architecture/llm-gateway.md](docs/architecture/llm-gateway.md).

## Data

The organizer dataset (synthetic, 13 tables, about 23.5 million rows) is never committed. What is in git is a bounded, pseudonymized sample of it: [data_platform/sample/README.md](data_platform/sample/README.md) shows every table's columns with example rows, and `data_platform/sample/preview/` has ten rows per table. The source is explicit and never mixed:

```bash
make pipeline                        # bronze, silver, gold from the committed sample: no network, no credentials
make data-download                   # with the organizer S3 values in .env: download the full 5.3 GB delivery
make pipeline DATA_SOURCE=s3         # build from it (or set BANK_DATA_SOURCE=s3 in .env)
make data-report && make lineage     # quality report and lineage (docs/data/ for the s3 source)
```

The [data card](docs/data/data-card.md) lists provenance, personal data handling, and the known issues found by profiling; the [data platform README](data_platform/README.md) has the commands and runtimes.

## Documentation

Start at the [documentation index](docs/README.md). Key entries: the [architecture overview](docs/architecture/overview.md), the [architecture decision records](docs/adr/README.md), [CONTRIBUTING.md](CONTRIBUTING.md), and [SECURITY.md](SECURITY.md).

## License

No license has been chosen yet. Until one is added, all rights are reserved by the authors.
