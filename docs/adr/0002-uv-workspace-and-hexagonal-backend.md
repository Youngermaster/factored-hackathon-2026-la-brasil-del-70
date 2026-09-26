# 0002: Monorepo with a uv workspace and hexagonal backend layers

- Status: accepted
- Date: 2026-09-26

## Context

The system has four Python codebases with different lifecycles (the API service, the data platform, the ML training code, and the evaluation harness) plus a web app. The brief rewards depth, verifiable behavior, and replaceable components: policy must be enforced outside model prose, models must be swappable, and the evaluation harness must run the same code as the API. The team needs every quality gate working from the first commit and one lockfile so versions cannot drift between packages.

## Considered options

### Repository shape

1. **Separate repositories** per package.
2. **One Python package** holding everything.
3. **A uv workspace monorepo**: one repository, one `uv.lock`, one virtual root with shared tool configuration, and four member packages (`bank-agent`, `bank-data`, `bank-ml`, `bank-evals`).

### Backend structure

1. **Framework-first layout** (routers call the ORM and model SDKs directly).
2. **Hexagonal layers** with inward-only imports: `domain` <- `ports` <- `policy` <- `application` <- `adapters` <- `api` and `bootstrap`, enforced by import-linter.

## Decision

A uv workspace monorepo with hexagonal backend layers.

- The root `pyproject.toml` is a virtual workspace root (no `[project]` table) holding the shared configuration for ruff, mypy, import-linter, pytest, coverage, and bandit, and the dev dependency group. Heavy ML libraries are added only when code uses them: scikit-learn, LightGBM, and MLflow to `bank-ml` in phase 10, and sentence-transformers in an optional `ml` extra of `bank-agent` in phase 07, never installed in the API runtime image.
- import-linter enforces three contracts: the layers contract; a pure-core contract forbidding `fastapi`, `sqlalchemy`, `httpx`, `boto3`, and `litellm` in `domain`, `ports`, and `policy`; and an entry-point contract.
- The layers contract makes `api` and `bootstrap` independent siblings, so neither may import the other. The wiring therefore lives in two package-root modules outside every layer: `bank_agent.asgi` (the uvicorn factory) and `bank_agent.cli`. No layer may import them. The API declares what it needs as the `ServiceProvider` Protocol and receives an `ApiConfig`; `bootstrap/container.py` satisfies the Protocol structurally and remains the only module that constructs adapters.
- mypy runs in strict mode for all first-party code, which covers and exceeds the four layers CLAUDE.md requires to be strict. It runs once over every package with `explicit_package_bases`, so the several `tests/` directories and `conftest.py` files get distinct module names; the root `conftest.py` is checked in a second run because it would collide with `services/api/tests/conftest.py`. Relaxations may only be per-module overrides for untyped third-party imports, never for `domain`, `ports`, `policy`, or `application`.
- Tests are classified by directory (`tests/unit/`, `tests/integration/`); unit tests run with the network blocked by pytest-socket. Coverage gates are per layer, enforced by a checker over the combined unit and integration report: 90% for `domain`, `ports`, `policy`, and `application`; 80% for `adapters`, `api`, `bootstrap`, and the three other packages.

## Consequences

- One `uv sync` installs everything, one lockfile pins everything, and a single `make check` gates all packages.
- Layer violations fail the build, and a negative-control test proves each contract actually fires.
- The indirection through `ServiceProvider` and the entry-point modules adds a little ceremony for each new dependency the API needs: a Protocol property plus its implementation in the container.
- Global strict typing can create friction with untyped libraries in later phases (dbt, MLflow); such cases are handled with per-module import overrides.
- Separate release cycles per package are not possible, which is acceptable for a single-team hackathon system.
