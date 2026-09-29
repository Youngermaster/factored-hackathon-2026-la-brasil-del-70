# Capacity

**Local measurement, not a production estimate.** The numbers below come from one run on one developer laptop, against the development stack, with no language model (`LLM_PROVIDER=fake`: every model call is refused at once and the deterministic path answers). They show the cost of the service's own work (routing, policy, tools, grounding, persistence, telemetry) and where it saturates first. They are not a capacity plan for a hosted deployment; phase 16 repeats the run on the target infrastructure.

## Configuration

| Item | Value |
|---|---|
| Date and commit | 2026-09-29, the phase 15 branch after `f77ad0d` |
| Machine | Apple M3, 8 cores, 16 GB, macOS; a local model evaluation (Ollama, `qwen2.5:7b-instruct`) was running at the same time and used roughly a third of one core |
| API | One uvicorn worker on the host (`uvicorn bank_agent.asgi:create_app --factory`), SQLAlchemy pool 5 plus 5 overflow, telemetry exported (`OTEL_ENABLED=true`, sampling 1.0) to the compose `obs` profile |
| Database | PostgreSQL 16 in Docker (compose image), seeded with `make seed` from the committed sample (200 customers) |
| Model | None (`LLM_PROVIDER=fake`, the default); the budget ledger is the PostgreSQL one |
| Rate limits | Raised to 100,000 per minute for the run (the defaults would refuse the load by design) |
| Tool | Locust 2.46.6 through `uv run --with` (`scripts/load/locustfile.py`, `make load-test`) |
| Traffic mix | Simulated customers per workflow weighted by the phase 04 demand shares: account inquiry 41, card support 26, dispute 24, credit 9; two in five conversations in Portuguese; each customer signs in once, then opens conversations of one to two turns with a 1 to 3 second pause; every turn is read only or stops before a write |
| Steps | 10, 25, and 50 concurrent customers, 60 seconds each |

## Results

Turn latency per workflow, in milliseconds (Locust, client side, including the HTTP round trip):

| Customers | Workflow | Turns | p50 | p95 | p99 |
|---|---|---|---|---|---|
| 10 | account_inquiry | 117 | 50 | 100 | 230 |
| 10 | card_support | 162 | 68 | 140 | 290 |
| 10 | dispute | 56 | 47 | 93 | 220 |
| 10 | credit | 27 | 71 | 140 | 300 |
| 25 | account_inquiry | 389 | 51 | 140 | 240 |
| 25 | card_support | 335 | 65 | 180 | 260 |
| 25 | dispute | 176 | 59 | 180 | 270 |
| 25 | credit | 57 | 52 | 220 | 280 |
| 50 | account_inquiry | 741 | 80 | 270 | 370 |
| 50 | card_support | 532 | 99 | 280 | 420 |
| 50 | dispute | 325 | 91 | 280 | 360 |
| 50 | credit | 133 | 86 | 330 | 470 |

Throughput and errors, all requests (sign-in, conversation opens, turns):

| Customers | Requests | Requests per second | Turns per second | p50 | p95 | Errors |
|---|---|---|---|---|---|---|
| 10 | 674 | 11.4 | 6.1 | 42 | 120 | 0 |
| 25 | 1,743 | 29.5 | 16.2 | 41 | 130 | 0 |
| 50 | 3,212 | 54.4 | 29.3 | 56 | 230 | 0 |

Credit turns are the slowest (they read the credit profile, estimate risk, and run the synthetic eligibility rules); account inquiries the fastest. No request failed at any step.

## Bottleneck

Throughput still grew linearly with the customers at 50 (the closed loop was not saturated), but latency tripled at p95 while the API process ran at about 80 percent of one core, and PostgreSQL at about 40 percent of one core. **The first bottleneck is the single Python worker's CPU** (one event loop does the routing, policy evaluation, rendering, grounding checks, JSON validation, and span export); the database connection pool (10 connections per worker) comes next. From the growth of latency, one worker on this machine tops out near 30 to 35 turns per second.

With a language model the picture changes, as the phase prompt expects: a turn makes about two model calls (signals and slot extraction; up to five with phrasing and handoff summaries), and each call took 3 to 6 seconds on the local 7B model (phase 14a: mean 3.7 s per call). Model latency then dominates the turn, workers spend their time waiting (cheap for an async worker), and **the provider's rate limits and concurrency become the bottleneck**, followed by the database connections held during long turns. Model calls are made outside database transactions, so a slow provider does not hold connections.

## Capacity estimate (projected from the local measurement)

Assumptions, labeled as such: a customer sends a turn every 20 seconds while chatting; the per-worker ceiling of about 30 turns per second holds on a comparable CPU; no model.

- One worker: about 30 turns per second, about 600 customers chatting at once.
- With a hosted model at about 2 calls per turn and a provider limit of N requests per second, the ceiling is about N / 2 turns per second, whatever the worker count; the daily budget (`LLM_DAILY_BUDGET_USD`) caps the model-served turns per day, and L2 (template-only) serves the rest.

These are projections, not measurements.

## How to scale each tier

| Tier | Limit today | How to scale |
|---|---|---|
| API workers | One process, CPU-bound near 30 turns per second | Run several uvicorn workers or containers behind Caddy. The budget ledger is already shared in PostgreSQL; the rate-limit counters and the active-session gauge are per process (shared limits are phase 16) |
| Database | 10 connections per worker, one PostgreSQL | Keep workers times pool size under `max_connections`, or add PgBouncer in transaction mode; move reads of the synthetic history to a replica if needed. Execution records and audit events grow without bound (a retention policy is phase 16) |
| Language model | Provider rate limits and latency | Request a higher quota, add `LLM_FALLBACK_MODEL` (L1), keep phrasing and summaries off (the defaults) to stay near two calls per turn, and rely on L2 when the budget or the provider runs out |
| Telemetry | Sampling 1.0, one collector | Lower `OTEL_TRACES_SAMPLER_ARG` (trace ids still reach the records), batch in the collector, persistent Jaeger storage in phase 16 |

## Reproduce

```bash
make up PROFILES=obs && make pipeline && make seed
RATE_LIMIT_WRITE_PER_MINUTE=100000 RATE_LIMIT_SESSION_WRITE_PER_MINUTE=100000 \
RATE_LIMIT_AUTH_PER_MINUTE=100000 RATE_LIMIT_SESSION_AUTH_PER_MINUTE=100000 make api-obs
make load-test LOAD_USERS=50 LOAD_DURATION=60s        # CSVs in reports/load/ (gitignored)
```

## Not measured

- A live provider under load (the only live runs are the phase 11 and 14 local model runs, one request at a time).
- Writes under load (card blocks, cases, intakes): they need step-up per customer and change the seeded data; their cost is a few more statements per turn.
- Several workers, a remote database, or TLS through Caddy (phase 16).
