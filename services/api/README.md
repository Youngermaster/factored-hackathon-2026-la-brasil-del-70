# bank-agent: API service

## Responsibility

`bank-agent` is the banking customer-service backend. The language model understands, deterministic code decides, and evidence proves it. The package holds the domain model, the ports, the policy kernel, the workflow engine, the adapters, and the FastAPI application, arranged as a hexagonal architecture.

## Layers

Imports flow inward only. import-linter enforces the contracts in the root `pyproject.toml`, and `make check` fails on any violation.

```mermaid
flowchart TD
    entry["asgi.py and cli.py<br/>entry points, outside the layers"]
    api["api<br/>FastAPI app, routers, DTOs, middleware"]
    bootstrap["bootstrap<br/>settings, logging, composition root"]
    adapters["adapters<br/>persistence, llm, retrieval, identity, models, telemetry"]
    application["application<br/>workflow engine, workflows, use cases"]
    policy["policy<br/>pack loader, rules, evaluator (pure)"]
    ports["ports<br/>Protocol interfaces"]
    domain["domain<br/>entities, value objects, errors (pure)"]
    entry --> api
    entry --> bootstrap
    api --> adapters
    bootstrap --> adapters
    adapters --> application
    application --> policy
    policy --> ports
    ports --> domain
```

An arrow means "may import". A layer may import any layer below it, not only the next one.

| Package | Responsibility | README |
|---|---|---|
| `domain` | Entities, value objects, enums, typed domain errors; no I/O | [domain](src/bank_agent/domain/README.md) |
| `ports` | Protocol interfaces for repositories, models, clocks, and checks | [ports](src/bank_agent/ports/README.md) |
| `policy` | Pure rules registered by id, the evaluator, the policy pack loader | [policy](src/bank_agent/policy/README.md) |
| `application` | Workflow engine, workflows, use cases | [application](src/bank_agent/application/README.md) |
| `adapters` | Implementations of the ports | [adapters](src/bank_agent/adapters/README.md) |
| `api` | FastAPI app factory, routers, middleware, problem details | [api](src/bank_agent/api/README.md) |
| `bootstrap` | Settings, logging, and the composition root | [bootstrap](src/bank_agent/bootstrap/README.md) |
| `prompts` | Versioned prompt files | [prompts](src/bank_agent/prompts/README.md) |
| `testing` | Deterministic test doubles (not a layer; production code never imports it) | [testing](src/bank_agent/testing/README.md) |

Three contracts apply:

1. **Layers:** `api | bootstrap` over `adapters` over `application` over `policy` over `ports` over `domain`. The `|` makes `api` and `bootstrap` independent: neither imports the other.
2. **Pure core:** `domain`, `ports`, and `policy` never import `fastapi`, `sqlalchemy`, `httpx`, `boto3`, or `litellm`.
3. **Entry points:** no layer imports `bank_agent.asgi` or `bank_agent.cli`.

## Entry points

Because `api` and `bootstrap` cannot import each other, the wiring lives in two package-root modules outside every layer:

- `bank_agent.asgi:create_app` is the uvicorn factory. It loads settings, configures logging, builds the container, and passes it to `bank_agent.api.app.create_app`.
- `bank_agent.cli:app` is the `bank-agent` typer command: `db upgrade`, `retention purge` (the owner's retention job; `--dry-run`, `--every-hours`), `policy lock`, `policy catalog`, `index build`.

Settings are validated per process: `load_settings()` checks the API's production rules (it refuses the owner password, requires the shared rate limiter, and allows demo mode only with `ALLOW_PUBLIC_DEMO_MODE=true`), and `load_settings(owner=True)` checks an owner job's (the owner password and `SESSION_SECRET` only).

The production images are `services/api/Dockerfile`: target `api` (the package with the `litellm` extra, the policy pack, the price table, the published evaluation summaries, and a stored retrieval index, running as a non-root user on a read-only root) and target `job` (plus `bank-data` and gold tables built from the committed sample, for migrations, the seed, and the purge). The deployment is `deploy/` ([guide](../../deploy/README.md)).

The API layer declares what it needs as the `ServiceProvider` Protocol in `api/provider.py`. The composition root, `bootstrap/container.py`, satisfies it structurally. It is the only module that constructs concrete adapters.

## Public interfaces

- HTTP: `GET /health/live` and `GET /health/ready`. Errors are RFC 9457 problem details (`application/problem+json`). Every response carries `X-Request-ID`.
- CLI: `bank-agent version`, `bank-agent db upgrade`, `bank-agent policy lock|catalog`, and `bank-agent index build` (the retrieval index for the current pack version), with `bank-agent --help`.
- Configuration: environment variables documented in the root `.env.example`, read only by `bootstrap/settings.py`.

Run the API locally:

```bash
uv run uvicorn bank_agent.asgi:create_app --factory --reload
# or, in containers with PostgreSQL:
make up PROFILES=api
```

## Dependencies and extras

Runtime dependencies are declared in `pyproject.toml` and pinned in the root `uv.lock`. The optional `ml` extra (phase 07) holds sentence-transformers 6.1.0 and torch 2.14.0 for the dense retriever, about 806 MB installed with their dependencies, torch from the PyTorch CPU index on Linux; it is never installed in the API runtime image or by `make setup` (`uv sync --all-packages --extra ml`). The optional `litellm` extra holds the provider client (ADR 0013). Opt-in Langfuse tracing uses the locked OpenTelemetry OTLP HTTP exporter; it adds no API dependency. See [observability](../../docs/operations/observability.md) for settings and startup.

## How to extend

- **Add an adapter:** implement the Protocol from `ports/` under `adapters/<area>/<technology>/`, add it to the shared contract suite in `tests/contracts/`, and select it in `bootstrap/container.py` from settings.
- **Add cross-cutting behavior:** wrap a port with a decorator that implements the same Protocol (retry, timeout, tracing, redaction) and stack it in the container. Never put it inside business code.
- **Add a setting:** add a field to the matching class in `bootstrap/settings.py`, document the variable in `.env.example`, and add a production rule if it is a secret.
- **Add an endpoint:** add a router under `api/routers/`, include it in `api/app.py`, and register any new error type in `api/problems.py`.
- **Add a rule or a prompt:** see the `policy` and `prompts` READMEs.

## How to test

```bash
uv run pytest services/api/tests -m unit          # no network, no database
uv run pytest services/api/tests -m integration   # PostgreSQL through testcontainers (Docker required)
make check                                        # everything, with coverage gates
```

- `tests/unit/` uses fakes and the httpx ASGI transport; pytest-socket blocks the network.
- `tests/integration/` starts a throwaway `postgres:16.15-alpine3.24` container with the repository init script and credentials generated at runtime. It never reads `.env`.
- Coverage gates: 90% for `domain`, `ports`, `policy`, and `application`; 80% for `adapters`, `api`, and `bootstrap`.

## Live human service

ADR 0026 adds persisted customer and assigned-agent messages on the existing conversation, and a rolling-hour customer creation quota. Existing databases need `make db-upgrade` (revision `0014`). The [human-service guide](../../docs/workflows/human-service.md) describes the endpoints, lifecycle, authorization, and local walkthrough.
