# Documentation index

Every document in the repository, grouped by purpose. Diagrams are Mermaid code blocks; `make docs-check` lints the Markdown and parses every diagram.

## Start here (judges)

| Document | Purpose |
|---|---|
| [../README.md](../README.md) | What the system is, the four workflows, the evaluation headline, the quickstart |
| [submission/brief-traceability.md](submission/brief-traceability.md) | Every requirement of the brief mapped to code, tests, docs, and evidence, per workflow |
| [submission/README.md](submission/README.md) | The submission package: checklist, draft email, pre-submission check |
| [submission/SUBMISSION.md](submission/SUBMISSION.md) | The submission checklist: what is done and the human steps in order |
| [submission/email-draft.md](submission/email-draft.md) | The draft email to the organizers (never sent by a session) |
| [../LIMITATIONS.md](../LIMITATIONS.md) | What the system cannot claim: scope, credit, data, language, evaluation, capacity, deployment, risks |
| [workflows/README.md](workflows/README.md) | Index of the workflow pages |
| [security/README.md](security/README.md) | Index of the security documents and the controls on one page |

## Working agreement and status

The [brief traceability matrix](submission/brief-traceability.md) is the shared reference for official requirements, implementation evidence, evaluation status, and known gaps. The [submission checklist](submission/SUBMISSION.md) tracks internal readiness and human steps, including the revised October 4 internal MVP completion window and the separate October 5 official challenge-window end.

| Document | Purpose |
|---|---|
| [CLAUDE.md](../CLAUDE.md) | Rules, stack, architecture, testing, documentation, and commit conventions for every session |
| [AGENTS.md](../AGENTS.md) | Guide for every coding agent: precedence, quick start, repository map, enforced rules, recipes for common changes, pitfalls, collaboration |
| [PROGRESS.md](PROGRESS.md) | Current state and the phase log: what was done, decisions, how to verify, limitations |
| [BACKLOG.md](BACKLOG.md) | Deferred items with the reason and the owning phase |
| [plans/](plans/) | The approved plan for each phase, and the team's kickoff notes (listed below) |
| [plans/adr-0026-live-agent.md](plans/adr-0026-live-agent.md) | Current-main and PR reference review, gaps, and implementation increments for live human service in the existing chat |
| [plans/kickoff-notes.md](plans/kickoff-notes.md) | The team's kickoff notes: roles and the scope decision |
| Phase plans | [00](plans/phase-00.md), [01](plans/phase-01.md), [02](plans/phase-02.md), [02b](plans/phase-02b.md), [03](plans/phase-03.md), [04](plans/phase-04.md), [05](plans/phase-05.md), [06](plans/phase-06.md), [07](plans/phase-07.md), [08](plans/phase-08.md), [09a](plans/phase-09a.md), [09b](plans/phase-09b.md), [10a](plans/phase-10a.md), [10b](plans/phase-10b.md), [11](plans/phase-11.md), [12](plans/phase-12.md), [13](plans/phase-13.md), [14a](plans/phase-14a.md), [14b](plans/phase-14b.md), [15](plans/phase-15.md), [16](plans/phase-16.md), [17](plans/phase-17.md), and [the local EDA](plans/eda-local.md) |

## Organizer material

| Document | Purpose |
|---|---|
| [organizer/BRIEF.md](organizer/BRIEF.md) | Summary of the hackathon brief and evaluation criteria |
| [organizer/DATA_DICTIONARY.md](organizer/DATA_DICTIONARY.md) | Dataset schema |

## Architecture

| Document | Purpose |
|---|---|
| [architecture/overview.md](architecture/overview.md) | System context, containers, the API's components, and the sequence of one customer turn |
| [architecture/domain-model.md](architecture/domain-model.md) | Domain class diagrams, case and credit application lifecycles, trust tiers, personal and internal data, error taxonomy |
| [architecture/ports-and-adapters.md](architecture/ports-and-adapters.md) | Ports, adapters present and planned, isolation rules, contract suites |
| [architecture/workflow-registry.md](architecture/workflow-registry.md) | The four workflows, the intents each owns, and what each answers, confirms, and escalates |
| [architecture/credit-separation.md](architecture/credit-separation.md) | Conversation handling, risk estimates, and the synthetic eligibility service kept apart |
| [architecture/llm-gateway.md](architecture/llm-gateway.md) | The language model port, providers, decorator stack, structured outputs, budgets, prices, tracing, and cassettes |
| [../contracts/README.md](../contracts/README.md) | JSON Schema contracts and their versioning rules |
| [design/DESIGN.md](design/DESIGN.md) | The design system: principles, type, spacing, color tokens with contrast, motion, data display, states, voice |
| [design/audit.md](design/audit.md) | The design pre-flight audit of the phase 12 foundation |
| [frontend/components.md](frontend/components.md) | The UI primitives and how to use them |
| [frontend/state.md](frontend/state.md) | Where every piece of frontend state lives (no Zustand) |
| [frontend/features.md](frontend/features.md) | The product features: composition diagrams, context boundaries, and TanStack Query data flow |
| [../apps/web/README.md](../apps/web/README.md) | The web app: layers, public interfaces, API client, how to extend and test |

## Architecture decision records

[adr/README.md](adr/README.md) is the index with the status and date of each record, and notes on the records whose scope the build does not follow.

| Record | Decision |
|---|---|
| [adr/0000](adr/0000-team-alignment-and-hackathon-strategy.md) | Agentic Banking Architecture, Core Tech Stack & Team Alignment |
| [adr/0001](adr/0001-record-architecture-decisions.md) | Record architecture decisions |
| [adr/0002](adr/0002-uv-workspace-and-hexagonal-backend.md) | Monorepo with a uv workspace and hexagonal backend layers |
| [adr/0003](adr/0003-frontend-layering-and-state.md) | Frontend layering and state rules |
| [adr/0004](adr/0004-money-and-currency-handling.md) | Money and currency handling |
| [adr/0005](adr/0005-trust-state-append-only.md) | Trust state as append-only evidence with a monotonic risk tier |
| [adr/0006](adr/0006-handoff-and-execution-record-contracts.md) | Handoff and execution record contracts, with no chain-of-thought field |
| [adr/0007](adr/0007-dbt-duckdb-and-pandera-for-the-data-platform.md) | dbt-duckdb and Pandera for the data platform |
| [adr/0008](adr/0008-server-side-opaque-sessions.md) | Server-side opaque sessions instead of JWT for the single-page app |
| [adr/0009](adr/0009-row-level-security-as-defense-in-depth.md) | Row-level security as defense in depth behind tool-layer scoping |
| [adr/0010](adr/0010-idempotency-keys-and-read-back-verification.md) | Idempotency keys and read-back verification for writes |
| [adr/0011](adr/0011-policy-as-data-and-pure-rule-functions.md) | Policy as data plus pure rule functions |
| [adr/0012](adr/0012-bound-policies-and-informational-retrieval.md) | Bound policies for workflow states, with open retrieval only for informational questions |
| [adr/0013](adr/0013-litellm-behind-a-port-with-composable-decorators.md) | LiteLLM behind a port with composable decorators |
| [adr/0014](adr/0014-explicit-state-machine-over-an-agent-framework.md) | An explicit state machine over an agent framework |
| [adr/0015](adr/0015-router-model-choice.md) | Router model choice |
| [adr/0016](adr/0016-resolver-approach.md) | Resolver approach |
| [adr/0018](adr/0018-design-system.md) | Design system on Radix primitives, Tailwind tokens, Phosphor icons, and the deck's typefaces |
| [adr/0019](adr/0019-single-host-compose-deployment.md) | A single-host Docker Compose deployment for the event, with a documented path to managed services |
| [adr/0020](adr/0020-four-workflows-and-the-workflow-registry.md) | Four workflows and the workflow registry |
| [adr/0021](adr/0021-credit-risk-and-eligibility-separation.md) | Separating conversation handling, risk estimates, and the synthetic eligibility service |
| [adr/0022](adr/0022-committed-bounded-data-sample.md) | A committed, bounded, pseudonymized organizer sample, and an explicit data source |
| [adr/0023](adr/0023-workflow-prioritization-method.md) | Pre-registered weighted scoring for workflow prioritization, with a labeled proxy while human labels are pending |
| [adr/0024](adr/0024-workflow-registry-with-router-dispatch.md) | A workflow registry with router dispatch over one generic engine |
| [adr/0025](adr/0025-tuesday-account-inquiry-mvp-and-observability.md) | Superseded historical Tuesday MVP plan: account inquiry, mock escalation, and assistant profile |
| [adr/0026](adr/0026-live-agent-joins-escalated-conversation.md) | Human escalation progresses from simulated replies to a human service agent joining the conversation |
| [adr/0027](adr/0027-opt-in-financial-memory-and-guidance.md) | Financial memory and guidance are opt-in and grounded |
| [adr/0028](adr/0028-mocked-multibank-and-digital-asset-surfaces.md) | Multi-bank connectors and digital-asset tabs start as mock surfaces |
| [adr/0029](adr/0029-in-domain-unsupported-requests.md) | In-domain unsupported requests are abstained by the owning workflow |
| [adr/0030](adr/0030-credit-risk-estimator.md) | Credit risk estimator: label, features, uncertainty, and separation from eligibility policy |
| [adr/0031](adr/0031-cookie-sessions-with-signed-double-submit-csrf.md) | Cookie sessions with signed double-submit CSRF for a same-site single-page app |
| [adr/0032](adr/0032-local-eda-and-progressive-viewer.md) | Local EDA with a progressive aggregate viewer |
| [adr/0033](adr/0033-sanitized-eda-laboratory.md) | Sanitized EDA laboratory in the local viewer |
| [adr/0034](adr/0034-bounded-local-gold-seed-for-mvp.md) | Bounded local gold seed into PostgreSQL for the MVP |
| [adr/0035](adr/0035-telemetry-export-and-degradation-ladder.md) | OpenTelemetry over OTLP HTTP, metrics from execution records, and a pure degradation ladder |

## Exploratory data analysis

| Document | Purpose |
|---|---|
| [analysis/EDA.md](analysis/EDA.md) | Reproducible local analysis, curation policies and Streamlit viewer |
| [analysis/RESULTS.md](analysis/RESULTS.md) | Aggregate findings from the completed local snapshot |
| [analysis/EDA_STANDARDS_REVIEW.md](analysis/EDA_STANDARDS_REVIEW.md) | EDA standards review and local-run provenance |
| [design/EDA.md](design/EDA.md) | Phase viewer and sanitized laboratory design |
| [plans/eda-local.md](plans/eda-local.md) | Approved implementation scope |

## Data

| Document | Purpose |
|---|---|
| [data/data-card.md](data/data-card.md) | Provenance, intended use, personal data handling, the credit balance sign convention, known issues, and the data-use terms check |
| [data/data-use.md](data/data-use.md) | The organizer data-use check for the committed sample: the human's confirmation, the reasoning, and the checks re-run |
| [data/source-layout.md](data/source-layout.md) | The organizer bucket layout, partitions, snapshots, and delivered row counts |
| [data/update-policy.md](data/update-policy.md) | Freshness targets, late arrivals, reprocessing and backfills, schema evolution, retention |
| [data/quality-report.md](data/quality-report.md) | Generated data-quality report of the latest full build |
| [data/lineage.md](data/lineage.md) | Generated lineage flowchart from the dbt manifest |
| [data/local-postgres-mvp.md](data/local-postgres-mvp.md) | Build gold from the local delivery, seed and verify the 200-customer MVP slice, and the plan for the full load |
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

## Policy

| Document | Purpose |
|---|---|
| [../policies/README.md](../policies/README.md) | The synthetic policy pack: format, synthetic disclaimer, how to add or change a clause, review, versioning |
| [policy/catalog.md](policy/catalog.md) | Generated table of every clause, rule, binding, action matrix row, and credit product |
| [policy/eligibility.md](policy/eligibility.md) | The synthetic eligibility rules per jurisdiction and product, the outcome mapping, and the review reasons |
| [workflows/policy-evaluation.md](workflows/policy-evaluation.md) | Evaluation order and precedence (flowchart) and a decision end to end (sequence) |
| [../services/api/src/bank_agent/policy/README.md](../services/api/src/bank_agent/policy/README.md) | The policy kernel package: interfaces, how to add a rule or a fact, how to test |

## Grounding and retrieval

| Document | Purpose |
|---|---|
| [workflows/grounding.md](workflows/grounding.md) | Bound lookup, drafting, verification, and fallback (sequence), the verifier checks, and which intents may use open retrieval |
| [../services/api/src/bank_agent/adapters/retrieval/README.md](../services/api/src/bank_agent/adapters/retrieval/README.md) | The retrievers, the index store, how to add a retriever and how to re-index |
| [evaluation/retrieval-labeling.md](evaluation/retrieval-labeling.md) | The relevance judgment format and the labeling and review protocol |
| [evaluation/retrieval.md](evaluation/retrieval.md) | Generated comparison of BM25, dense, and hybrid retrieval, by workflow, language, and jurisdiction |

## Learned components

| Document | Purpose |
|---|---|
| [../ml/README.md](../ml/README.md) | How to add, train, evaluate, promote, retrain, and compare a learned model |
| [models/router.md](models/router.md) | Model card of the intent router (TF-IDF and embeddings against the keyword baseline) |
| [models/resolver.md](models/resolver.md) | Model card of the transaction resolver (LightGBM ranker against the rule baseline) |
| [models/risk-estimator.md](models/risk-estimator.md) | Model card of the credit risk estimator (snapshot risk estimate; logistic regression and LightGBM against the score-band baseline) |
| [evaluation/router.md](evaluation/router.md) | Generated router evaluation: per intent, language, locale, and workflow, calibration, robustness, transfer |
| [evaluation/resolver.md](evaluation/resolver.md) | Generated resolver evaluation: per use, language, country, candidate count, clue, silver labels |
| [evaluation/risk-estimator.md](evaluation/risk-estimator.md) | Generated risk estimator evaluation: test metrics with intervals, calibration, bands, interval coverage, slices and disparities |
| [evaluation/router-labeling.md](evaluation/router-labeling.md) | The protocol for the 200-item router validation sample |
| [evaluation/README.md](evaluation/README.md) | The scenario evaluation harness (Mermaid) and its commands, including the local-model runs of session 14b |
| [evaluation/plan.md](evaluation/plan.md) | The phase 14 evaluation plan: systems, mix, splits, metrics, statistics, run protocol, budget, decisions |
| [evaluation/methodology.md](evaluation/methodology.md) | Definitions, splits and leakage prevention, customers, graders, statistics, judge validation, limitations |
| [evaluation/judge-rubric.md](evaluation/judge-rubric.md) | The judge's rubric and the human rating protocol |
| [evaluation/results.md](evaluation/results.md), [evaluation/failures.md](evaluation/failures.md) | Generated by `bank-eval publish`: per workflow, aggregate, routing, slices, repeated runs, H, and the failure table |

## Workflow engine and workflows

| Document | Purpose |
|---|---|
| [workflows/workflow-router.md](workflows/workflow-router.md) | One turn end to end (flowchart), dispatch and switch rules, the registry, guarantees, and baseline B0 |
| [workflows/dispute-intake.md](workflows/dispute-intake.md) | Dispute state machine, state to rules, clauses, and tools, sequences for the normal, ambiguous, and escalation paths, and the confirmation and abstention matrix |
| [workflows/card-support.md](workflows/card-support.md) | Card support state machine, state table, sequences, and matrix |
| [workflows/account-inquiry.md](workflows/account-inquiry.md) | Account inquiry state machine (read only), state table, as-of dates, sequences, and matrix |
| [workflows/credit-information.md](workflows/credit-information.md) | Credit state machine, the separation of conversation, risk estimate, and eligibility, the score-band baseline, sequences, and matrix |
| [workflows/human-service.md](workflows/human-service.md) | Live customer and assigned-agent messages, lifecycle, isolation, quota, and verification |
| [workflows/handoff.md](workflows/handoff.md) | The handoff schema walkthrough, worked examples, and what agents see |
| [workflows/execution-records.md](workflows/execution-records.md) | Execution record fields, storage, and explaining a decision without chain-of-thought |
| [../services/api/src/bank_agent/application/README.md](../services/api/src/bank_agent/application/README.md) | How to add a state, a workflow, or a tool |

## HTTP API

| Document | Purpose |
|---|---|
| [api/README.md](api/README.md) | Endpoint catalog (method, path, role, CSRF, rate class), the auth model, error types, and versioning |
| [../contracts/openapi.json](../contracts/openapi.json) | The committed OpenAPI contract (`make openapi`), source of the web client types |

## Operations

| Document | Purpose |
|---|---|
| [operations/observability.md](operations/observability.md) | Telemetry flow, the signal catalog, log retention, and how to read the trace of one conversation |
| [operations/degradation.md](operations/degradation.md) | The degradation ladder L0 to L4: triggers, behavior, flags, customer wording, and the chaos tests |
| [operations/runbook.md](operations/runbook.md) | Each alert mapped to its symptom, diagnosis, and action |
| [operations/capacity.md](operations/capacity.md) | The local load test: p50 and p95 per workflow, throughput, the bottleneck, and how to scale each tier |
| [plans/phase-15.md](plans/phase-15.md) | The phase 15 plan and its decided questions |
| [../deploy/README.md](../deploy/README.md) | The single-host deployment guide: AWS Lightsail, EC2, Azure VM, DNS, firewall, the env file, deploy, update, back up, restore, roll back, take down |
| [plans/phase-16.md](plans/phase-16.md) | The phase 16 plan: deployment topology, hardening checklist, and decided questions |

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
| [deploy](../deploy/README.md) | The production stack, the deployment guide, database roles, and observability configuration |
| [slides](../slides/README.md) | The pitch deck: commands, structure, colour meaning, numbers from `data/metrics.yml`, export |
| Backend layers | [domain](../services/api/src/bank_agent/domain/README.md), [ports](../services/api/src/bank_agent/ports/README.md), [adapters](../services/api/src/bank_agent/adapters/README.md), [api](../services/api/src/bank_agent/api/README.md), [bootstrap](../services/api/src/bank_agent/bootstrap/README.md), [testing](../services/api/src/bank_agent/testing/README.md) |
| Web layers | [app](../apps/web/src/app/README.md), [pages](../apps/web/src/pages/README.md), [features](../apps/web/src/features/README.md), [entities](../apps/web/src/entities/README.md), [shared](../apps/web/src/shared/README.md) |

## Contributing and security

| Document | Purpose |
|---|---|
| [security/prompt-injection.md](security/prompt-injection.md) | Prompt injection defense layers, their status, and their tests |
| [security/identity-and-sessions.md](security/identity-and-sessions.md) | The mock identity service, one-time codes, sessions, step-up, lifetimes and limits |
| [security/data-isolation.md](security/data-isolation.md) | Tool-layer scoping, row-level security, database roles and policies, and the tests that prove them |
| [security/threat-model.md](security/threat-model.md) | STRIDE per component across the deployed topology, abuse cases, mitigations linked to code and tests, and residual risks |
| [security/demo-mode.md](security/demo-mode.md) | Why the public demo shows one-time codes on screen, what that exposes, and what a real deployment does instead |
| [security/data-retention.md](security/data-retention.md) | What is kept, for how long, the purge job, and what a regulated deployment would change |
| [security/data-use.md](security/data-use.md) | Which fields reach which model provider and why, redaction, provider retention, and the committed sample |
| [demo/personas.md](demo/personas.md) | Demo personas: selection criteria, what each demonstrates, and how to seed and log in |
| [demo/script.md](demo/script.md) | Outline of the demo scenes for the video: inputs checked through the API, and what each proves |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | How to set up, change, test, and commit |
| [SECURITY.md](../SECURITY.md) | Scope and how to report a vulnerability |

Every Markdown file under `docs/` is listed here; a new document gets its row in the same commit.
