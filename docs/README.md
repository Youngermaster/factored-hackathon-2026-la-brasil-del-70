# Documentation index

Every document in the repository, grouped by purpose. Diagrams are Mermaid code blocks; `make docs-check` lints the Markdown and parses every diagram.

## Working agreement and status

| Document | Purpose |
|---|---|
| [CLAUDE.md](../CLAUDE.md) | Rules, stack, architecture, testing, documentation, and commit conventions for every session |
| [PROGRESS.md](PROGRESS.md) | Current state and the phase log: what was done, decisions, how to verify, limitations |
| [BACKLOG.md](BACKLOG.md) | Deferred items with the reason and the owning phase |
| [plans/](plans/) | The approved plan for each phase, and the team's kickoff notes |

## Organizer material

| Document | Purpose |
|---|---|
| [organizer/BRIEF.md](organizer/BRIEF.md) | Summary of the hackathon brief and evaluation criteria |
| [organizer/DATA_DICTIONARY.md](organizer/DATA_DICTIONARY.md) | Dataset schema |

## Architecture

| Document | Purpose |
|---|---|
| [architecture/overview.md](architecture/overview.md) | Monorepo components and their dependency direction |
| [architecture/domain-model.md](architecture/domain-model.md) | Domain class diagrams, case and credit application lifecycles, trust tiers, personal and internal data, error taxonomy |
| [architecture/ports-and-adapters.md](architecture/ports-and-adapters.md) | Ports, adapters present and planned, isolation rules, contract suites |
| [architecture/workflow-registry.md](architecture/workflow-registry.md) | The four workflows, the intents each owns, and what each answers, confirms, and escalates |
| [architecture/credit-separation.md](architecture/credit-separation.md) | Conversation handling, risk estimates, and the synthetic eligibility service kept apart |
| [architecture/llm-gateway.md](architecture/llm-gateway.md) | The language model port, providers, decorator stack, structured outputs, budgets, prices, tracing, and cassettes |
| [../contracts/README.md](../contracts/README.md) | JSON Schema contracts and their versioning rules |
| [adr/README.md](adr/README.md) | Index of architecture decision records |
| [adr/0001](adr/0001-record-architecture-decisions.md) | Record architecture decisions |
| [adr/0002](adr/0002-uv-workspace-and-hexagonal-backend.md) | Monorepo with a uv workspace and hexagonal backend layers |
| [adr/0003](adr/0003-frontend-layering-and-state.md) | Frontend layering and state rules |
| [adr/0004](adr/0004-money-and-currency-handling.md) | Money and currency handling |
| [adr/0005](adr/0005-trust-state-append-only.md) | Trust state as append-only evidence with a monotonic risk tier |
| [adr/0006](adr/0006-handoff-and-execution-record-contracts.md) | Handoff and execution record contracts, with no chain-of-thought field |
| [adr/0007](adr/0007-dbt-duckdb-and-pandera-for-the-data-platform.md) | dbt-duckdb and Pandera for the data platform |
| [adr/0013](adr/0013-litellm-behind-a-port-with-composable-decorators.md) | LiteLLM behind a port with composable decorators |
| [adr/0020](adr/0020-four-workflows-and-the-workflow-registry.md) | Four workflows and the workflow registry |
| [adr/0021](adr/0021-credit-risk-and-eligibility-separation.md) | Separating conversation handling, risk estimates, and the synthetic eligibility service |
| [adr/0022](adr/0022-committed-bounded-data-sample.md) | A committed, bounded, pseudonymized organizer sample, and an explicit data source |
| [adr/0023](adr/0023-workflow-prioritization-method.md) | Pre-registered weighted scoring for workflow prioritization, with a labeled proxy while human labels are pending |

## Data

| Document | Purpose |
|---|---|
| [data/data-card.md](data/data-card.md) | Provenance, intended use, personal data handling, the credit balance sign convention, known issues, and the data-use terms check |
| [data/source-layout.md](data/source-layout.md) | The organizer bucket layout, partitions, snapshots, and delivered row counts |
| [data/update-policy.md](data/update-policy.md) | Freshness targets, late arrivals, reprocessing and backfills, schema evolution, retention |
| [data/quality-report.md](data/quality-report.md) | Generated data-quality report of the latest full build |
| [data/lineage.md](data/lineage.md) | Generated lineage flowchart from the dbt manifest |
| [workflows/data-pipeline.md](workflows/data-pipeline.md) | Source to serving flowchart and the incremental run with a late arrival |
| [../data_platform/sample/README.md](../data_platform/sample/README.md) | The committed organizer sample: provenance, counts, treatments, and example rows per table |

## Analysis and decisions

| Document | Purpose |
|---|---|
| [analysis/README.md](analysis/README.md) | Index of the phase 04 reports, how to regenerate them, and the dataset version |
| [analysis/workflow-scoring-preregistration.md](analysis/workflow-scoring-preregistration.md) | Criteria, weights, formulas, rubrics, and rules, committed before any score |
| [analysis/workflow-evidence.md](analysis/workflow-evidence.md) | Generated demand, outcome, pattern, cost, segment, and data support evidence per workflow |
| [analysis/workflow-scores.md](analysis/workflow-scores.md) | Generated scores, ranking, weight and mapping sensitivity, and sub-intent classes |
| [analysis/labeling-protocol.md](analysis/labeling-protocol.md) | The automatable-share labeling task and the transcript limitation |
| [decisions/workflow-prioritization.md](decisions/workflow-prioritization.md) | Build and depth order, sub-intent classes, breadth risk, and what would change the order |
| [../data_platform/analysis/README.md](../data_platform/analysis/README.md) | The analysis inputs (scoring, cost assumptions, reason mapping) and code map |

## Packages and apps

| README | Scope |
|---|---|
| [services/api](../services/api/README.md) | API service and its layer READMEs |
| [apps/web](../apps/web/README.md) | Web application and its layer READMEs |
| [data_platform](../data_platform/README.md) | Data platform: sources, commands, how to add a table or a source adapter |
| [ml](../ml/README.md) | Learned components |
| [evals](../evals/README.md) | Evaluation harness |
| [evals/cassettes](../evals/cassettes/README.md) | Language model cassettes (hand-authored fixtures until a provider is chosen) |
| [services/api/src/bank_agent/prompts](../services/api/src/bank_agent/prompts/README.md) | Versioned prompts: format, rules, how to add, test, and evaluate one |
| [deploy](../deploy/README.md) | Database roles and observability configuration |

## Contributing and security

| Document | Purpose |
|---|---|
| [security/prompt-injection.md](security/prompt-injection.md) | Prompt injection defense layers, their status, and their tests |
| [security/identity-and-sessions.md](security/identity-and-sessions.md) | The mock identity service, one-time codes, sessions, step-up, lifetimes and limits |
| [security/data-isolation.md](security/data-isolation.md) | Tool-layer scoping, row-level security, database roles and policies, and the tests that prove them |
| [demo/personas.md](demo/personas.md) | Demo personas: selection criteria, what each demonstrates, and how to seed and log in |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | How to set up, change, test, and commit |
| [SECURITY.md](../SECURITY.md) | Scope and how to report a vulnerability |

Later phases add the workflow pages to `docs/workflows/`, and `docs/evaluation/`, `docs/operations/`, `docs/frontend/`, and `docs/design/`, each listed here when it lands.
