# Architecture decision records

Each record captures one choice between real alternatives, in the [MADR](https://adr.github.io/madr/) format: context, options, decision, and consequences. Records are numbered in order and never rewritten; a later record supersedes an earlier one and both link to each other.

Numbers 0015 to 0019 are reserved for the phases that already name them, so the table lists records by number, not by date.

| Number | Title | Status | Date |
|---|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted | 2026-09-26 |
| [0002](0002-uv-workspace-and-hexagonal-backend.md) | Monorepo with a uv workspace and hexagonal backend layers | Accepted | 2026-09-26 |
| [0003](0003-frontend-layering-and-state.md) | Frontend layering and state rules | Accepted | 2026-09-26 |
| [0004](0004-money-and-currency-handling.md) | Money and currency handling | Accepted | 2026-09-26 |
| [0005](0005-trust-state-append-only.md) | Trust state as append-only evidence with a monotonic risk tier | Accepted | 2026-09-26 |
| [0006](0006-handoff-and-execution-record-contracts.md) | Handoff and execution record contracts, with no chain-of-thought field | Accepted | 2026-09-26 |
| [0007](0007-dbt-duckdb-and-pandera-for-the-data-platform.md) | dbt-duckdb and Pandera for the data platform | Accepted | 2026-09-26 |
| [0008](0008-server-side-opaque-sessions.md) | Server-side opaque sessions instead of JWT for the single-page app | Accepted | 2026-09-27 |
| [0009](0009-row-level-security-as-defense-in-depth.md) | Row-level security as defense in depth behind tool-layer scoping | Accepted | 2026-09-27 |
| [0010](0010-idempotency-keys-and-read-back-verification.md) | Idempotency keys and read-back verification for writes | Accepted | 2026-09-27 |
| [0011](0011-policy-as-data-and-pure-rule-functions.md) | Policy as data plus pure rule functions, with the synthetic eligibility service on the same kernel | Accepted | 2026-09-27 |
| [0012](0012-bound-policies-and-informational-retrieval.md) | Bound policies for workflow states, with open retrieval only for informational questions | Accepted | 2026-09-27 |
| [0013](0013-litellm-behind-a-port-with-composable-decorators.md) | LiteLLM behind a port with composable decorators | Accepted | 2026-09-26 |
| [0014](0014-explicit-state-machine-over-an-agent-framework.md) | An explicit state machine over an agent framework | Accepted | 2026-09-27 |
| [0015](0015-router-model-choice.md) | Learned routers (TF-IDF and embeddings) behind the port, rule baseline as the default until end-to-end evaluation | Accepted | 2026-09-27 |
| [0016](0016-resolver-approach.md) | A LightGBM lambdarank resolver with labels by construction, an evidence gate, and a none-of-these option | Accepted | 2026-09-27 |
| [0020](0020-four-workflows-and-the-workflow-registry.md) | Four workflows and the workflow registry | Accepted | 2026-09-26 |
| [0021](0021-credit-risk-and-eligibility-separation.md) | Separating conversation handling, risk estimates, and the synthetic eligibility service | Accepted | 2026-09-26 |
| [0022](0022-committed-bounded-data-sample.md) | A committed, bounded, pseudonymized organizer sample, and an explicit data source | Accepted | 2026-09-26 |
| [0023](0023-workflow-prioritization-method.md) | Pre-registered weighted scoring for workflow prioritization, with a labeled proxy while human labels are pending | Accepted | 2026-09-26 |
| [0024](0024-workflow-registry-with-router-dispatch.md) | A workflow registry with router dispatch over one generic engine | Accepted | 2026-09-27 |
| [0025](0025-tuesday-account-inquiry-mvp-and-observability.md) | Tuesday MVP includes account inquiry, mock escalation, and assistant profile | Accepted | 2026-09-27 |
| [0026](0026-live-agent-joins-escalated-conversation.md) | Human escalation progresses from simulated replies to a human service agent joining the conversation | Accepted | 2026-09-27 |
| [0027](0027-opt-in-financial-memory-and-guidance.md) | Financial memory and guidance are opt-in and grounded | Accepted | 2026-09-27 |
| [0028](0028-mocked-multibank-and-digital-asset-surfaces.md) | Multi-bank connectors and digital-asset tabs start as mock surfaces | Accepted | 2026-09-27 |
| [0029](0029-in-domain-unsupported-requests.md) | In-domain unsupported requests are abstained by the owning workflow | Accepted | 2026-09-27 |
| [0030](0030-credit-risk-estimator.md) | A cross-sectional snapshot risk estimate: label, allowlisted features, dev-chosen intervals, and policy bands, kept apart from eligibility | Accepted | 2026-09-27 |
| [0032](0032-local-eda-and-progressive-viewer.md) | Local EDA and progressive aggregate viewer | Accepted | 2026-09-27 |
| [0033](0033-sanitized-eda-laboratory.md) | Sanitized EDA laboratory in the local viewer | Accepted | 2026-09-27 |

## Adding a record

1. Copy the structure of an existing record into `NNNN-short-title.md` with the next number.
2. Describe the context and at least two real options with their trade-offs.
3. State the decision and its consequences, including what becomes harder.
4. Add a row to the table above in the same commit as the change it records.
