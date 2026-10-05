# Brief traceability matrix

Every requirement of the organizer brief ([summary](../organizer/BRIEF.md)) mapped to where it is implemented, where it is proven, and its status. Workflow-level requirements get one column per workflow, so a gap in one workflow is visible. Written in phase 17 at the state of `main` after the phase 17 fixes; the evaluation evidence is the run `test-hosted` at `2ddabb0` of 2026-10-05 (simulated, offline, `azure/gpt-4.1-mini`, before the final-day QA fixes; [results](../evaluation/results.md)); the local 14b run is archived in `runs/test-local`. Since 2026-10-05 the deployed demo calls Azure OpenAI `gpt-4.1-mini` (fallback `gpt-4o`).

Status values: **Proven** (a test, a report, or a check in `make check` shows it), **Proven, simulated** (shown by the evaluation harness on the synthetic world), **Limitation** (not met or only partly met, stated in [LIMITATIONS.md](../../LIMITATIONS.md)), **Human step** (outside the code; see [SUBMISSION.md](SUBMISSION.md)).

Paths are relative to the repository root. `tests/` means `services/api/tests/`; `workflows/` means `services/api/tests/integration/workflows/`; "guide" means the demo guide scenario of that id (`apps/web/src/features/demo-guide/model/scenarios.ts`), each driven through the API in es and in pt on a fresh sample seed in phase 17.

## 1. The challenge

| Requirement | Implemented in | Proven by | Status |
|---|---|---|---|
| A customer-service system, not a chatbot: understand, decide, act, verify, escalate | One engine with explicit state machines per workflow (`services/api/src/bank_agent/application/engine/`, `application/workflows/`); [ADR 0014](../adr/0014-explicit-state-machine-over-an-agent-framework.md) | [Architecture overview](../architecture/overview.md) (turn sequence); `workflows/` scenario tests | Proven |
| Understand complex customer interactions | Structured understanding through the LLM gateway with deterministic fallbacks; slang, amounts, relative dates, card endings (`application/understanding/`, `application/workflows/dispute/understand.py`) | `workflows/test_dispute_model_guesses.py`, `test_credit_model_guesses.py`; routing correct 271/304 (89%) for P | Proven, simulated |
| Use data and tools securely | Tools from a per-state allowlist, customer injected from the session, row-level security ([data isolation](../security/data-isolation.md)) | `tests/contracts/test_read_tools_contract.py`, `test_write_tools_contract.py`, `tests/integration/test_row_level_security.py` | Proven |
| Complete appropriate service workflows | Four workflows ([workflow pages](../workflows/README.md)) | `workflows/` scenario tests; the per-workflow tables in [results](../evaluation/results.md) | Proven, simulated |
| Involve human agents when needed | Structured handoffs, the agent inbox, claim and resolve ([handoff](../workflows/handoff.md)) | `tests/integration/api/test_agent_and_evaluation.py`, `test_handoff_policy_excerpts.py`; missed transfers 7/64 for P | Proven, simulated |
| One focused workflow, depth over breadth | Four workflows by human decision, each at the same depth bar ([ADR 0020](../adr/0020-four-workflows-and-the-workflow-registry.md)) | Per-workflow evaluation slices; this matrix's per-workflow columns | Limitation (scope risk stated) |
| Spanish and Portuguese | Customer copy and templates in es and pt; policy clauses in es, pt, en | Guide scenarios in both; es 188 and pt 116 evaluation cases; locale parity tests | Proven; native pt review pending |

## 2. Required demonstration cases, per workflow

| Case | `account_inquiry` | `card_support` | `dispute` | `credit` |
|---|---|---|---|---|
| Normal resolution | Balances with the as-of date: guide `balances`; scenario 19 (es-AR) in `workflows/test_account_inquiry.py` | Protective block with confirmation, step-up, read-back: guide `card-block`; scenario 14 (es-CO) in `workflows/test_card_and_routing.py` | Case opened on a confirmed charge: guide `dispute-intake`; status with the deadline: guide `dispute-status`; scenario 1 (es-MX) in `workflows/test_dispute_normal.py` | Catalog and an indicative result: guide `credit-eligibility`, `credit-status`; scenario 25 (pt-BR) in `workflows/test_credit_workflow.py` |
| Ambiguous or unsupported | Payment without details: guide `payment-details`; a transfer request abstained: guide `transfer-unsupported`; scenario 20 (pt-BR, two similar transfers) | Which card: guide `card-status`; scenario 13 (pt-BR) | Charge without details: guide `dispute-details`; scenario 3 (pt-BR) | Missing income: guide `credit-missing-income`; a demand for approval abstained: guide `credit-approval-request`; `workflows/test_credit_edges.py` |
| Human intervention | Contested balance: guide `contested-balance`; scenario 23 (es-CO) | Unblock request: guide `card-unblock`; scenario 16 (pt-BR, replacement) | Complaint to the regulator: guide `dispute-regulator`; amount above the automatic limit: scenario 6 (es-MX), [handoff example](../workflows/handoff.md) | Borderline or incomplete result sent to review: guide `credit-review`; scenario 27 in `workflows/test_credit_workflow.py`; every credit path in `test_credit_separation.py` |
| In es and pt | Every guide scenario in both (phase 17 drive); 47 es and 29 pt test cases | Same | Same | Same |
| Evaluated separately | [results](../evaluation/results.md) `account_inquiry`: 76 cases | `card_support`: 76 cases | `dispute`: 76 cases | `credit`: 76 cases |
| Status | Proven | Proven | Proven | Proven |

## 3. Minimum requirements, per workflow

| Requirement | `account_inquiry` | `card_support` | `dispute` | `credit` | Shared implementation and proof |
|---|---|---|---|---|---|
| Maintain conversational context | Chosen product kept for follow-ups | Chosen card kept; carried into a dispute on switch | Slots merged across turns (`dispute/understand.py`) | Amount, term, and product kept across turns | Persisted conversation state and pending steps; `workflows/test_engine_behaviors.py`, `test_pending_answer_signals.py`; switches confirmed mid-flow ([router](../workflows/workflow-router.md)) |
| Clarify ambiguous requests | Which product or payment | Which card | Which transaction (at most three options) | Which product, missing facts | CLARIFY states with a clarification budget; `workflows/test_workflow_choice_answers.py` |
| Retrieve trusted information | Balances, payments, statements from repositories with as-of dates | Card status from records | Case status from records | Synthetic catalog; eligibility from the synthetic service | Bound clauses per state and Qdrant hybrid retrieval (BM25 fused with Azure text-embedding-3-small; BM25 fallback) for informational questions, grounding verifier with template fallback ([grounding](../workflows/grounding.md), [retrieval results](../evaluation/retrieval.md), provisional labels) |
| Use tools securely | Read tools only | `block_card` allowlisted only in its state | `create_dispute_case`, optional `block_card` | `submit_credit_application` only after review consent | Session-injected customer, tool argument validation, per-state allowlist; `tests/contracts/test_*_tools_contract.py`; `workflows/test_third_party_requests.py` |
| Execute appropriate workflows | Read-only resolution | Protective block | Case intake and status | Information, indication, intake | [Workflow pages](../workflows/README.md); safe automated resolution per workflow in [results](../evaluation/results.md) |
| Verify that actions happened | No writes | Read-back before "Verificado" | Read-back before the case number | Read-back of the intake | Idempotency keys and `WriteVerifier` read-backs ([ADR 0010](../adr/0010-idempotency-keys-and-read-back-verification.md)); `workflows/test_success_needs_verification.py`; false success claims 0/304 for P |
| Know when not to act | Transfers, official statements: abstain (`ACC-ALL-3`) | Unblock and replacement: hand off | Outside the window, above the limit, another currency: hand off or abstain | Limit increases, restructuring, disbursement, a credit decision: abstain (`CRE-ALL-3`); no approval outcome | Clause-backed abstentions ([ADR 0029](../adr/0029-in-domain-unsupported-requests.md)); `workflows/test_unsupported_before_clarify.py`, `test_denials_and_follow_ups.py` |
| Hand off to a human when needed | Contested balance, a request for a person | Unblock, replacement | SLA breach, limit, repeat complainer, regulator | Review required, missing data, contested result | Handoff with request, verified facts, actions, evidence, open questions, no transcript ([handoff](../workflows/handoff.md)); handoff completeness 55/57 for P |
| Status | Proven | Proven | Proven | Proven | |

## 4. The three expected outcomes by case type

| Case | Expected handling | Implemented in | Proven by | Status |
|---|---|---|---|---|
| Normal | Policy-compliant automated resolution, verified account queries, authorized self-service transactions | Read states with as-of dates; writes behind confirmation, step-up, and read-back | Safe automated resolution 185/304 (61%) for P on the hosted run, per workflow 58%, 63%, 59%, 63%; policy compliance 294/304 | Proven, simulated |
| Ambiguous or unsupported | Clarifying questions, or safe abstention for missing parameters or unsupported requests | CLARIFY states; clause-backed abstentions; out-of-scope answers | Guide ambiguous scenarios; routing scenarios 24/28 correct for P ([results](../evaluation/results.md)); out-of-scope requests answered with a workflow question instead of an abstention are a known weakness (BACKLOG, 14c) | Proven, with a stated weakness |
| Human-required | Structured handoff with verified facts and open questions, no raw transcript | `domain/handoff.py`, the handoff builder, the agent inbox | Missed transfers 7/64, handoff completeness 55/57 for P; `contracts/schemas/handoff.v1.json` has no transcript field ([ADR 0006](../adr/0006-handoff-and-execution-record-contracts.md)) | Proven, simulated |

## 5. What the solution should demonstrate

| # | Requirement | Implemented in | Proven by | Status |
|---|---|---|---|---|
| 1 | A problem supported by data: contact reasons, demand, data quality, operational constraints; prioritization; intended outcomes | `data_platform/src/bank_data/analysis/`, pre-registered scoring | [workflow evidence](../analysis/workflow-evidence.md), [scores](../analysis/workflow-scores.md), [pre-registration](../analysis/workflow-scoring-preregistration.md), [prioritization](../decisions/workflow-prioritization.md), [quality report](../data/quality-report.md) | Proven (offline); automatable-share human labels pending (action 11) |
| 2 | Context and clarification; grounded factual responses; tools when they serve; report only verified actions | Engine, grounding verifier, tools, read-backs | Sections 3 and 4; the verifier and fallback in [grounding](../workflows/grounding.md) | Proven |
| 3 | Controlled automation: what it answers, what needs confirmation, when to abstain or transfer; permissions outside model prose; handoff content | `policies/matrix.yaml` (action matrix), `policies/bindings.yaml`, the policy kernel | [policy catalog](../policy/catalog.md); confirmation and abstention matrix on each workflow page; `tests/unit/policy/` | Proven |
| 4 | Repeatable data preparation with contracts, quality checks, lineage, update policy | Pandera contracts, dbt-duckdb bronze, silver, gold, quarantine | [data card](../data/data-card.md), [lineage](../data/lineage.md), [update policy](../data/update-policy.md), [pipeline](../workflows/data-pipeline.md); `data_platform/tests/integration/test_update_correctness.py` (late partition, labeled fixture) | Proven |
| 4 | At least one learned component against a baseline; valid labels; no leakage; justified representations, metrics, thresholds, splits | Router (TF-IDF, embeddings vs keyword), resolver (LightGBM vs rules), risk estimator (logreg, LightGBM vs score bands), retrieval (BM25, dense, hybrid, Qdrant, Qdrant hybrid; pre-registered switch passed) | [router](../models/router.md), [resolver](../models/resolver.md), [risk estimator](../models/risk-estimator.md), [retrieval](../evaluation/retrieval.md); leakage guards in `ml/`; ADRs [0015](../adr/0015-router-model-choice.md), [0016](../adr/0016-resolver-approach.md), [0030](../adr/0030-credit-risk-estimator.md) | Proven offline; human labels for router validation and retrieval pending (actions 19, 27) |
| 5 | Held-out evaluation including incorrect or missing data, expired sessions, unauthorized access, prompt injection, tool failures, multilingual ambiguity | `evals/` scenario families per category; the failure injector | [results](../evaluation/results.md), [failures](../evaluation/failures.md), [methodology](../evaluation/methodology.md); the chaos suite in [degradation](../operations/degradation.md) | Proven, simulated |
| 5 | Successful and unsafe outcomes, handoffs, latency, cost, with sample sizes and limitations | `bank-eval publish` | [results](../evaluation/results.md) (per workflow, then aggregate, with denominators and intervals) | Proven, simulated |
| 6 | Tracing, bounded retries, safe fallback, reproducible setup | OpenTelemetry, the decorator stack (retry, timeout, breaker, budget), the degradation ladder, `make` targets | [observability](../operations/observability.md), [degradation](../operations/degradation.md), [LLM gateway](../architecture/llm-gateway.md); the README quickstart | Proven |
| 6 | Capacity limits, monitoring, access controls, retention, remaining deployment work | Alerts, the load test, RBAC and RLS, the purge job, ADR 0019 | [capacity](../operations/capacity.md), [runbook](../operations/runbook.md), [security](../security/README.md), [retention](../security/data-retention.md), [LIMITATIONS](../../LIMITATIONS.md#deployment-work-remaining) | Proven; deployed on one Azure VM with the `obs` profile, Key Vault secrets, and the purge job; the load test is measured on a laptop only |
| 6 | Explanations from sources, rules, execution records; no hidden chain-of-thought | Execution records with rule ids, clause versions, tool calls, verification results | [execution records](../workflows/execution-records.md); the glass box; the record schema has no reasoning field | Proven |

## 6. Data and execution boundaries

| Requirement | Implemented in | Proven by | Status |
|---|---|---|---|
| Only organizer-approved data; identify real, de-identified, synthetic, team-generated inputs; follow the data-use terms | Explicit data sources (`sample`, `s3`, `local`); labels in the data card | [data card](../data/data-card.md), [data-use record](../data/data-use.md) (human confirmation, 2026-09-30) | Proven |
| No private records, credentials, or restricted data in the public submission or in model requests | The bounded pseudonymized sample; prompt input allowlists; redaction | `scripts/checks/check_data_sample.py`, gitleaks over the history, `tests/unit/adapters/llm/test_redaction.py`, the forbidden-variable check in the prompt registry | Proven |
| Sandbox services and mock tools with documented contracts and limits | Mock identity service, demo OTP sender, tool contracts | [identity and sessions](../security/identity-and-sessions.md), [ports and adapters](../architecture/ports-and-adapters.md), [demo mode](../security/demo-mode.md) | Proven |
| Authentication by a trusted test session; a national ID or customer number alone never proves identity | One-time codes over a keyed identity lookup; step-up before writes | `tests/integration/api/test_auth_flow.py`; [identity and sessions](../security/identity-and-sessions.md) | Proven |
| Access to each customer's records and action permissions enforced in the service or tool layer | Session-injected customer, per-state allowlist, 404 for other customers, forced RLS | `tests/integration/test_row_level_security.py`, `tests/integration/test_database_roles.py`, cross-customer API tests | Proven |
| No live lending decisions or movement of money | No approval outcome exists; no money-moving tool exists | The `EligibilityOutcome` enum (no approved value); the tool list in `domain/actions.py` | Proven |

### Credit rows

| Requirement | Implemented in | Proven by | Status |
|---|---|---|---|
| Separate conversation handling, predictive risk estimates, and eligibility policy | `RiskEstimator` and `EligibilityPolicy` ports; the conversation only receives the eligibility result's reasons | [credit separation](../architecture/credit-separation.md), [ADR 0021](../adr/0021-credit-risk-and-eligibility-separation.md); `workflows/test_credit_separation.py` (a recording `FakeLLM` proves no prompt carries the estimate or the profile) | Proven |
| Approved rules or a clearly labeled synthetic policy service | The synthetic eligibility service over `ELG` rules in `policies/`; "synthetic" in every customer text, the glass box, and the catalog | [eligibility](../policy/eligibility.md); golden texts in `tests/integration/policy/golden/` | Proven; human review of thresholds pending (action 17) |
| The model does not invent eligibility rules | Rules are pure functions with parameters in files; the model never selects or phrases the outcome | `policies/versions.lock.yaml`; `tests/unit/policy/test_eligibility_service.py`; prompt inputs never carry the credit profile or the risk estimate (the prompt registry refuses them) | Proven |
| The model does not approve credit | No approved outcome by design; an approval-wording lexicon in es, pt, en rejects credit texts (`policy/lexicon.py`) | Credit approval claims 0/304 for P (B1: 28/304); `tests/unit/policy/test_approval_lexicon.py` | Proven, simulated |
| Explanations | Every eligibility answer lists its reasons with the rule and clause that back each | Guide `credit-eligibility`; [credit workflow](../workflows/credit-information.md) | Proven |
| Uncertainty | The estimate's interval and the boundary flag become a reason ("near a boundary, so the result is uncertain") | `ELG-ALL-2`; `workflows/test_credit_edges.py` | Proven |
| Review paths | Every result offers a person; borderline and missing data go to review; agents take and close intakes | Guide `credit-review`; `tests/integration/api/test_agent_credit_review.py` | Proven |
| No live decisions | Intakes are recorded for human review only | The About page (`/about`), the credit clauses, and the intake confirmation text | Proven |

## 7. Evaluation evidence

| Requirement | Where | Status |
|---|---|---|
| Baseline and proposed system on the same held-out workload | B0, B1, P on the frozen test split (332 scenarios, lock checked) | Proven, simulated |
| Number and mix of cases, label quality, model and prompt versions, repeated-run variability | [results](../evaluation/results.md) header, scenario review status, repeated runs (48 scenarios, 3 runs) | Proven; labels not yet human-reviewed (action 41) |
| Failures included | [failures](../evaluation/failures.md); the unsafe outcomes read case by case in results | Proven |
| A model judge with a rubric validated against human or deterministic judgments | [judge rubric](../evaluation/judge-rubric.md); the judge never decides success or safety | Limitation: human agreement pending (action 40) |
| Safe automated resolution over all in-scope cases, plus the attempted share | 185/304 with 270/304 attempted, per workflow in results | Proven, simulated |
| Containment never alone | Reported next to resolution and transfers everywhere | Proven |
| Escalation quality: missed and unnecessary transfers | 7/64 missed, 27/240 unnecessary for P, per workflow | Proven, simulated |
| Unsafe outcomes with counts and denominators; zero is not zero risk | Counts, exact intervals, rule-of-three bounds | Proven, simulated |
| p50 and p95 latency, cost per attempted case and per resolution, with assumptions | Per turn and per case; measured on Azure `gpt-4.1-mini` at list price (P 0.0013 USD per attempted case, 0.0019 per resolution); a monthly volume figure labeled projected | Proven, simulated and projected |
| By language and authorized segment; small samples; disparities investigated | Slices by language, dialect, segment; 44 slice gaps listed; 43 not established (small samples); 1 flagged as supported (P, dispute, premium segment, 0 of 4 against 62% for the rest), on 4 cases, under investigation | Proven, small samples |
| Offline, simulation, and projection labeled apart; no offline result called a production improvement | Labels in results, the README, the evaluation view, and `slides/data/metrics.yml` (`kind`) | Proven |

## 8. Submission requirements

| Requirement | Where | Status |
|---|---|---|
| Public GitHub repository named `factored-hackathon-2026-[team name]` | `factored-hackathon-2026-la-brasil-del-70` | Human step: make it public |
| A link to where the tool is deployed | [deploy/README.md](../../deploy/README.md); the URL is in `slides/data/metrics.yml` (`deploy.url`) and the email | Done: <https://la-brasil-del-70.westus2.cloudapp.azure.com>, one Azure VM, continuous deployment from `main` with a smoke test, a CSP check, and automatic rollback ([ADR 0038](../adr/0038-continuous-deployment-to-azure-with-github-actions.md)) |
| A 4 to 6 slide presentation | [slides/](../../slides/README.md): six main slides, each tagged with the evaluation dimensions it answers; the appendix exports to a separate PDF | Human step: `pnpm export:final` (no metric pending); the pitch PDF has exactly six pages, one per slide, and a separate 32-page version has one page per build-up step |
| A video pitch of 3:00 at most, demonstrating the solution and the core architectural decisions | [video plan](../demo/video-plan.md), [video monologue](../demo/video-monologue.md), [practice cases](../demo/practice-cases.md), [slides/VIDEO.md](../../slides/VIDEO.md); `pnpm check:content` fails past 3:00 of narration | Human step: record and export, final cut 3:00 or less |
| Everything to `hackathon.admin@factored.ai` by 2026-10-05 | [email-draft.md](email-draft.md) | Human step: send by 23:59 Colombia time (UTC-5), the team's cutoff, since the public page gives only the date |
