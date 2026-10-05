# Architecture decision records

Each record captures one choice between real alternatives, in the [MADR](https://adr.github.io/madr/) format: context, options, decision, and consequences. Records are numbered in order and never rewritten; a later record supersedes an earlier one and both link to each other.

The table lists records by number, not by date: 0015 to 0019 were reserved early for the phases that named them. 0017 was never used and stays reserved, so no record takes it. The status column repeats each record's own status line; the notes below the table say where the build departs from a record, without changing the record.

| Number | Title | Status | Date |
|---|---|---|---|
| [0000](0000-team-alignment-and-hackathon-strategy.md) | Agentic banking architecture, core tech stack, and team alignment (the team's alignment record) | Proposed (see the notes) | 2026-09-27 |
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
| [0018](0018-design-system.md) | Design system on Radix primitives, Tailwind tokens, Phosphor icons, and the deck's typefaces | Accepted | 2026-09-29 |
| [0019](0019-single-host-compose-deployment.md) | A single-host Docker Compose deployment for the event, with a documented path to managed services | Accepted | 2026-09-29 |
| [0020](0020-four-workflows-and-the-workflow-registry.md) | Four workflows and the workflow registry | Accepted | 2026-09-26 |
| [0021](0021-credit-risk-and-eligibility-separation.md) | Separating conversation handling, risk estimates, and the synthetic eligibility service | Accepted | 2026-09-26 |
| [0022](0022-committed-bounded-data-sample.md) | A committed, bounded, pseudonymized organizer sample, and an explicit data source | Accepted | 2026-09-26 |
| [0023](0023-workflow-prioritization-method.md) | Pre-registered weighted scoring for workflow prioritization, with a labeled proxy while human labels are pending | Accepted | 2026-09-26 |
| [0024](0024-workflow-registry-with-router-dispatch.md) | A workflow registry with router dispatch over one generic engine | Accepted | 2026-09-27 |
| [0025](0025-tuesday-account-inquiry-mvp-and-observability.md) | Historical Tuesday MVP plan: account inquiry, mock escalation, and assistant profile | Superseded | 2026-09-27 |
| [0026](0026-live-agent-joins-escalated-conversation.md) | Human escalation progresses from simulated replies to a human service agent joining the conversation | Accepted | 2026-09-27 |
| [0027](0027-opt-in-financial-memory-and-guidance.md) | Financial memory and guidance are opt-in and grounded | Accepted | 2026-09-27 |
| [0028](0028-mocked-multibank-and-digital-asset-surfaces.md) | Multi-bank connectors and digital-asset tabs start as mock surfaces | Accepted | 2026-09-27 |
| [0029](0029-in-domain-unsupported-requests.md) | In-domain unsupported requests are abstained by the owning workflow | Accepted | 2026-09-27 |
| [0030](0030-credit-risk-estimator.md) | A cross-sectional snapshot risk estimate: label, allowlisted features, dev-chosen intervals, and policy bands, kept apart from eligibility | Accepted | 2026-09-27 |
| [0031](0031-cookie-sessions-with-signed-double-submit-csrf.md) | Cookie sessions with signed double-submit CSRF for a same-site single-page app | Accepted | 2026-09-27 |
| [0032](0032-local-eda-and-progressive-viewer.md) | Local EDA and progressive aggregate viewer | Accepted | 2026-09-27 |
| [0033](0033-sanitized-eda-laboratory.md) | Sanitized EDA laboratory in the local viewer | Accepted | 2026-09-27 |
| [0034](0034-bounded-local-gold-seed-for-mvp.md) | Bounded local gold seed into PostgreSQL for the MVP | Accepted | 2026-09-27 |
| [0035](0035-telemetry-export-and-degradation-ladder.md) | OpenTelemetry over OTLP HTTP, metrics from execution records, and a pure degradation ladder | Accepted | 2026-09-29 |
| [0036](0036-grafana-live-analytics-separate-from-offline-evaluation.md) | Provisioned Grafana for live analytics, separate from offline evaluation | Accepted | 2026-10-03 |
| [0037](0037-cloud-secret-management-with-azure-key-vault.md) | Production secrets in Azure Key Vault with workload identity | Accepted | 2026-09-30 |
| [0038](0038-continuous-deployment-to-azure-with-github-actions.md) | Continuous deployment to the Azure VM with GitHub Actions, GHCR, OIDC, and run-command | Proposed | 2026-10-04 |
| [0039](0039-azure-vm-data-pipeline.md) | Execute the existing data pipeline on an Azure VM | Accepted | 2026-10-03 |
| [0040](0040-isolated-bank-database-vm.md) | Isolate the data pipeline on vm-bank-database in westus2 | Accepted | 2026-10-04 |
| [0041](0041-data-engineering-deployment-and-datagrip.md) | Data engineering deployment, validation, and DataGrip access | Accepted; Azure naming replacement superseded | 2026-10-04 |
| [0042](0042-preserve-azure-resource-names.md) | Keep Azure resource names and organize data engineering | Accepted | 2026-10-04 |
| [0046](0046-customer-service-history-vector-retrieval.md) | Customer-service history uses consented vector retrieval (renumbered teammate draft) | Proposed | 2026-10-05 |
| [0047](0047-qdrant-vector-index-for-knowledge-retrieval.md) | Qdrant vector index for customer-service knowledge retrieval | Accepted | 2026-10-05 |

## Notes on status

- **0000** was merged from the team repository during phase 05 (only its whitespace changed so `make docs-check` passes). It is the team's alignment record and states some things the phase log does not record elsewhere (for example a ten-day window and a feature lock on day 1). Its status stays as its authors wrote it, Proposed; whether the team accepts it is its authors' call (pending action 14 in [PROGRESS.md](../PROGRESS.md)).
- **0025** is superseded: the human decided on 2026-09-27 that the build does not follow its narrower release scope, and all four workflows stay automated. Its mock human agent was not built. The assistant profile and privacy-safe, metadata-only Langfuse export later landed independently in PRs 18 and 20; Langfuse remains opt-in and disabled by default. Neither capability reinstates the superseded release plan.
- **0026** is implemented and verified in the `feat/adr-0026-live-agent` increment: customer and assigned-agent messages on the original conversation, truthful lifecycle states, closure, and the customer creation quota. See [the channel guide](../workflows/human-service.md) and [PROGRESS](../PROGRESS.md) for verification. **0027 and 0028** remain optional future directions (opt-in financial memory, mock multi-bank and digital-asset surfaces); neither is built or part of the settled MVP scope.
- **0015, 0016, and 0030** keep their defaults "until phase 14 measures the learned models end to end". Session 14b did, on the dev split with the local model, and kept the rule baselines (`keyword@1`, `rules@1`, `score_band@1`); the evidence is in [results.md](../evaluation/results.md#decision-the-learned-router-resolver-and-risk-estimator-defaults-dev-evidence-only).
- **0022** asks for the organizer data-use terms to be checked before the repository becomes public; phase 17 recorded the check in [data-use.md](../data/data-use.md).

## Adding a record

1. Copy the structure of an existing record into `NNNN-short-title.md` with the next number.
2. Describe the context and at least two real options with their trade-offs.
3. State the decision and its consequences, including what becomes harder.
4. Add a row to the table above in the same commit as the change it records.
