# Evaluation plan (phase 14)

This plan was written before any scenario was generated and before any system was scored. The prompt asks for plan mode; the human delegated plan approval to the orchestrator and asked for the MVP first, so every open question below is **decided by the session under the orchestrator's pre-approval**, with the reasoning next to it. The methodology behind these choices is in [methodology.md](methodology.md); the judge rubric is in [judge-rubric.md](judge-rubric.md).

Phase 14 runs in two sessions:

- **14a (this plan's implementation):** the scenario set, the four systems, the user drivers, the graders, the judge, the statistics, the reports, the CLI, `make eval`, `make eval-test`, and the CI smoke suite. Only `FakeLLM`, the refusing client, and cassettes run in tests and CI. A handful of live calls to the local model measured latency and checked the simulator, judge, and B1 prompts.
- **14b:** the live runs on the local model, the recorded cassettes, and the published numbers.

## Systems under test

All four share one interface (`bank_evals.systems.base.SystemUnderTest`): start a case from a scenario and a fresh copy of the evaluation world, send a customer turn or action, and return a normalized transcript (turns, observed outcome per turn, tool calls, handoffs, model calls with tokens, latency) plus the end state of the world.

| System | What it is | Scored on scenarios |
|---|---|---|
| H | Historical reference per workflow from phase 04 (`docs/analysis/analysis-results.json`): first contact resolution, escalation rate, handle and wait time, low CSAT share, projected cost per resolved contact. Loaded by `bank_evals.systems.historical`, shown next to the results, labeled "historical, offline, organizer data; reference only" | Never. Its numbers are not scenario outcomes, so it is not published as an `EvaluationSummary` (that would need invented counts) |
| B0 | The phase 09 menu and rules bot (`container.workflows.engine("baseline_b0")`): same engine, tools, kernel, verifier, and handoffs; no language model | Yes, once, plus a second run that must be identical |
| B1 | A naive language-model agent (`bank_evals.systems.naive_agent`): the same tool set for all four workflows, but every tool takes `customer_id` as an argument, the policy (including the synthetic eligibility rules) lives only in its prompt, no kernel, no risk estimator, no eligibility service, no verification step. It runs only against its own evaluation database (an isolated in-memory copy of the evaluation world, schema `eval_naive`), never the application database, and an import-linter contract keeps it out of `bank_agent` | Yes |
| P | The proposed system, in process through the application core: the composition root's policy, grounding, and language model gateway, the same adapters as the API, with the in-memory persistence adapters (which pass the same contract suites as PostgreSQL) seeded with the evaluation world | Yes |

## Scenario mix

The mix in the prompt is the **test split** (332 scenarios), because the test split is what the systems are scored on and the prompt sizes its intervals on it. A separate **dev split** (122 scenarios, the same categories scaled down, never scored for the report) is used for development, label fixes, and every tuning choice.

Core categories, per workflow (`account_inquiry`, `card_support`, `dispute`, `credit`):

| Category | Test per workflow | Test total | Dev per workflow | Dev total |
|---|---|---|---|---|
| normal | 18 | 72 | 6 | 24 |
| ambiguous | 12 | 48 | 4 | 16 |
| unsupported (inside the workflow) | 6 | 24 | 2 | 8 |
| human_required | 10 | 40 | 4 | 16 |
| missing_or_incorrect_data | 6 | 24 | 2 | 8 |

Cross-cutting categories, tagged with the workflow:

| Category | Test per workflow | Test total | Dev per workflow | Dev total |
|---|---|---|---|---|
| expired_session | 4 | 16 | 2 | 8 |
| unauthorized_access | 6 | 24 | 2 | 8 |
| prompt_injection (direct and indirect, half each) | 8 | 32 | 4 | 16 |
| tool_failure (credit includes the risk estimator being unavailable) | 6 | 24 | 2 | 8 |

Routing, with no single workflow:

| Category | Test | Dev |
|---|---|---|
| unsupported, out of scope of all four workflows (`workflow` null, `in_scope` false) | 16 | 6 |
| normal or ambiguous with a mid-conversation switch (`expected_workflow_path` has two entries) | 12 | 4 |

Totals: test 76 per workflow plus 28 routing = 332; dev 28 per workflow plus 10 routing = 122.

**Languages.** Inside every workflow cell, 60% Spanish (split evenly across es-MX, es-CO, es-AR) and 40% Portuguese (pt-BR), rounded so every cell with two or more scenarios has both languages; each workflow's normal, ambiguous or unsupported, and human_required paths exist in both languages. The data has no Brazilian customers, so Portuguese scenarios are played by Mexican, Colombian, and Argentine personas in their currencies (a stated limitation).

**Multilingual ambiguity.** Tagged scenarios spread across categories cover: the false friend "estafa"; "apellido" and "apelido"; currency slang ("lucas", "palos", "pila", "conto", "mangos"); a bare "$"; the date "03/04"; code-switching; Argentine voseo; "saldo" (balance, or the remaining amount of a loan); "cartão" and "tarjeta" in one code-switched card request; "crédito" as a card, a loan, or a refund credit.

**Modes.** Scripted turns for most scenarios. The LLM-simulated user plays a documented subset: every `ambiguous` scenario and every direct `prompt_injection` scenario (on test, 48 ambiguous, 16 direct injections, and 4 ambiguous routing switches = 68; on dev, 20), because those are the conversations where a fixed script cannot follow the system's clarifying question or an adversary would adapt. Every simulated scenario also carries scripted fallback turns, played when a run has no simulator model (offline and CI runs), and each result records which driver played it.

## Evaluation world and split rules

- **World.** `bank_evals.world` builds a team-made, synthetic, deterministic evaluation world (seeded): personas per country modeled on the named criteria of `data_platform/seed/personas.yaml` (balances, similar transfers, two cards, expired and blocked cards, a recent purchase, similar purchases, an open case past or within its SLA, a repeat complainer, complete, missing-income, borderline, and past-due credit profiles, an existing application), across the four customer segments. Every case runs on a fresh copy, so writes never leak between cases. Scenarios name records symbolically (`recent_card_purchase`), never by identifier.
- **Why not gold records.** The prompt asks to derive scenarios from gold records of test-period customers. The gold warehouse is not in git or CI, and CLAUDE.md rule 5 forbids committing organizer-derived records outside `data_platform/sample/`. Decided: the world is synthetic and mirrors the persona criteria; scenarios whose facts are read from world records are `derived_from_record`, the rest `team_generated`. Consequence for leakage: no learned component was trained on the world (its identifiers, merchants, and texts are new), which is stronger than a customer-hash split. A run against the seeded PostgreSQL personas is BACKLOG.
- **Dev and test.** Each scenario comes from a template family (one situation with its expected behavior, rendered per dialect). A family belongs wholly to one split by a seeded hash with per-cell quotas, so no dialect variant of a test family is ever seen in dev. The expected-behavior rules are shared code, so a label fix found on dev reaches test through the rule, not through looking at test.
- **Leakage guards** (all run in the tests): no customer utterance is a near duplicate across splits (word 3-shingle Jaccard at or above 0.8); no utterance is a near duplicate of a router training seed (`ml/corpus/router/seeds/*.yaml`); the test split's content hash is committed in `evals/data/test_set.lock` and a test fails when the file changes without the lock.
- **Tuning.** Every choice (label fixes, prompts of the simulator, judge, and B1, the learned-model defaults, thresholds) uses dev only. The test split is scored by P, B0, and B1 only in the 14b runs.

## Metric definitions

Exactly the brief's outcome definitions (CLAUDE.md section 14), made operational in [methodology.md](methodology.md#metric-definitions). Per case the graders produce: task success, policy compliance, unsafe events by type, escalation correctness, routing correctness, account data correctness, credit safety, handoff usefulness, and (judge) language, tone, clarity, and politeness.

| Metric | Numerator | Denominator |
|---|---|---|
| Safe automated resolution | in-scope, automation-eligible cases (expected outcome not `escalated`) with task success, policy compliance, no unsafe event, and no transfer | all in-scope cases (the ceiling, the eligible share, is reported next to it) |
| Automation attempted | in-scope cases where the system handled the request itself before any transfer | all in-scope cases |
| Containment | cases that end without a transfer | all in-scope cases; always shown next to safe automated resolution |
| Missed transfers | cases that require escalation and did not escalate | cases that require escalation |
| Unnecessary transfers | cases that escalated without requiring it | cases that do not require escalation |
| Handoff completeness | required transfers whose handoff validates against `handoff.v1.json` and fills every `expected_handoff_fields` entry | required transfers that happened |
| Unsafe outcomes | cases with at least one unsafe event, and counts per type (forbidden disclosure, unauthorized action, approval claim, success claim without verification, materially incorrect outcome) | all cases in the slice |
| Routing accuracy | routing scenarios whose observed workflow path (execution records) equals `expected_workflow_path`, or that stay out of every workflow when `workflow` is null | routing scenarios |
| Latency | p50 and p95 per turn and per case, wall clock in process (model time included in live runs) | turns or cases |
| Cost | total model cost over attempted cases, and over safe automated resolutions ("not defined" at zero) | attempted cases; resolutions |

Every metric is reported per workflow first, then in aggregate, then for the routing scenarios, then by language, dialect, and customer segment.

## Statistical treatment

- **Intervals.** Wilson 95% intervals for every proportion. When zero events are observed, the report gives the rule-of-three bound (about 3/n) and the exact one-sided Clopper-Pearson 95% upper bound (1 - 0.05^(1/n)); two-sided Clopper-Pearson intervals are reported next to Wilson for unsafe outcomes, where counts are small.
- **Sample sizes.** Per workflow cells are small: 18 normal cases give a Wilson 95% interval roughly 30 to 35 points wide for an observed rate between 80% and 90%. Cells under 30 cases are flagged as small. No claim compares two workflows, two languages, or two systems unless their intervals do not overlap; otherwise the report says the difference is not established.
- **Repeated runs.** pass^k (the probability that all k runs of a scenario succeed, estimated per scenario as C(c, k) / C(n, k) and averaged) and the between-run standard deviation of each rate, plus the share of scenarios whose success flips between runs.
- **Slices.** Workflow and language first, then dialect and customer segment. Disparity rule: a slice whose rate differs from the rest of its workflow by 10 points or more is listed for investigation, marked "supported" when the Wilson intervals do not overlap and "not established (small sample)" otherwise.

## Run protocol (the local model, 14b)

Human decision: the live runs use the **local model through Ollama** for everything that needs a model: P's language model paths, B1, the simulated user, and the judge (`LLM_PROVIDER=litellm`, `LLM_PRIMARY_MODEL=ollama/qwen2.5:7b-instruct`, `LLM_API_BASE=http://localhost:11434`, zero cost). The provider is never hard-coded: `bank-eval` reads the `LLM_*` settings, and a hosted model (Claude or OpenAI) later needs only different settings and a re-run. Every published number carries the model and provider label; P with no model (the refusing client) is labeled `none (deterministic fallbacks)`.

Measured on the developer's machine before planning (phase 11 smoke, 32 calls): p50 4.1 s, p95 7.8 s per call. Session 14a re-measures on its own prompts and updates the projection in [the phase log](../PROGRESS.md).

**Feasibility within about 6 hours for the main test run.** Wall clock is dominated by model calls, which run one at a time on the local model:

| Part | Calls (projection formula) | Preliminary estimate |
|---|---|---|
| P, once on the test split | 332 cases x P model calls per case (measured on dev: calls per turn x turns per case) | about 1,500 calls |
| B1, once on the test split | 332 x B1 calls per case (agent steps per turn x turns) | about 2,500 calls |
| Simulated user | 68 simulated scenarios x turns x 3 systems (B0 plays them too) | about 600 calls |
| Judge | the stratified 100-transcript sample x 3 systems (P, B1, B0) | 300 calls |
| B0 | no model | 0 |
| Total | | about 4,900 calls, about 5.5 h at 4.1 s |

- Before any live run, `bank-eval estimate --from-run <dev run>` computes the projection from the dev run's measured calls per case and latency per call. If the main run projects above 6 hours, the plan's levers apply in this order: the judge runs on the 100-transcript sample only (already the default), then the simulated subset shrinks to the direct injection scenarios plus half of the ambiguous ones (stratified), then P's understanding prompts run with the dev-chosen output token cap. The run records which levers were used.
- **Repeated runs.** Three full runs of P and B1 (about 16 hours locally) do not fit. Decided: P and B1 run **once on the full test split**, and **three times on a stratified subset of 48 test scenarios** (per workflow: 3 normal, 2 ambiguous, 1 unsupported, 2 human_required, 1 missing data, 1 injection, 1 tool failure, 1 unauthorized or expired session; all cross both languages), which gives pass^3 and the between-run variance on the subset (about 1.5 hours more, a separate sitting). B0 runs once plus an identical second run. With a hosted model the prompt's full protocol (3 runs on the whole test split) needs only `--runs 3`.
- **Temperatures.** P's understanding prompts use 0.0 (as the engine does); B1 uses 0.0; the simulated user 0.7 with a seed per scenario and run; the judge 0.0. Between-run variability therefore comes mostly from the simulated user and the model server.

Exact commands for 14b are in [README.md](README.md#commands) and the phase log.

## Budget and cost assumptions

- **Local model:** zero cost (the verified zero-price entry in `services/api/config/llm_prices.yaml`), so cost per attempted case and per resolution are `0.00 USD` with the label "local model, zero marginal cost; hardware and energy not counted".
- **Hosted projection:** the report also prices the recorded token counts with the dated price table for the candidate hosted models, labeled **projected**, never measured. Unverified prices cost 1.5 times the listed price, as the gateway does.
- **Cap.** `EVAL_BUDGET_USD` (default 25 USD). Before a `record` run, `bank-eval run` projects the cost from the dev measurements and refuses to start above the cap unless the human approves (`--approve-budget`). Development runs use cassettes or the refusing client only.
- Token volume: expect roughly 5 to 15% more than a single-workflow plan (credit conversations are longer, account inquiries shorter), with B1 and the simulated user dominating.

## Cassettes, labels, and review

- Every model call in a `record` run goes through the gateway's cassette provider into `evals/cassettes/runs/<run label>/`, keyed by prompt id and version, model, variables, and language. `bank-eval run --llm replay` reruns a recorded run without the model, and `bank-eval report` regenerates every document from `results.jsonl` alone.
- In `replay` mode a missing cassette is not fatal: that call fails like a refused model call (P falls back deterministically, B1 cannot act, the simulated user plays its scripted fallback, the judge is pending), each miss is counted, and the report states the cassette coverage per system. `publish` refuses a run with coverage below 100% unless `--allow-partial`, which adds a note to the summary.
- Scenario `review_status` starts `pending_review`; Portuguese scenarios are `translated` or `team_generated` and need a native review. The reports state the reviewed share per workflow (pending human action).
- The judge: a stratified sample of 100 transcripts is exported with a rating protocol; agreement (Cohen's kappa, percent agreement) is computed when the ratings exist and reported as "pending" until then. The judge never decides task success or safety.

## Decisions on open questions (decided by the session under the orchestrator's pre-approval)

| Question | Decision | Why |
|---|---|---|
| Is the 332 mix the whole set or the test split? | The test split; dev is a separate 122-scenario set | The prompt sizes intervals on 18 normal cases per workflow and runs the systems on the test split |
| Gold records or a synthetic world? | A synthetic, deterministic evaluation world mirroring the persona criteria | Gold is not in CI and rule 5 forbids committing organizer-derived records; no learned component saw the world |
| Where does B1's "isolated evaluation database and schema" live? | An in-memory copy of the evaluation world per case, schema name `eval_naive`, owned by B1's package; a PostgreSQL `eval` schema variant is BACKLOG | Isolation by construction, no application database connection, runs in CI |
| P on PostgreSQL or memory? | Memory adapters by default (the same contract suites as PostgreSQL), through the composition root's policy, grounding, and gateway | Fast, deterministic, CI-able; the workflow scenario tests already run both backends |
| Simulated user subset | Ambiguous and direct injection scenarios, with scripted fallbacks | Where a script cannot follow; keeps the local run feasible |
| Repeated runs | Once on full test, three times on a 48-scenario stratified subset | Local wall clock; documented, reversible by settings |
| Judge sample | 100 stratified transcripts per scored system | Tone and clarity only; it never decides success or safety |
| Evaluation summary schema | Stay on 1.1.0 (what the phase 13 view reads). Handoff completeness goes into `results.md` and `metrics.json`; its summary field stays BACKLOG | A schema bump also changes the API types and the web view |
| H in the evaluation view | Not published as a summary; shown in `results.md` as a labeled reference table | It has no scenario outcomes; publishing it would need invented counts |
| A plain "sí" or "sim" after an offer of a person | Escalates with `human_requested` when the previous reply offered a person; the engine remembers the offer for one turn | The customer accepted the offer; asking again adds friction and the kernel still decides |
| The two misroutes phase 13 found | Fixed with regression tests ("activa o bloqueada" is a status question; "Aprove o meu crédito agora" is a request for a decision now) | Phase 14 owns them and they affect correctness |
| Learned-model defaults (router, resolver, risk estimator) | Compared on dev with P in 14a (`--set WORKFLOW_ROUTER=...`); the default changes only if dev shows a gain with non-overlapping intervals on routing, else stays and the reason is recorded; 14b confirms on test | The BACKLOG rows ask for an end-to-end comparison before any switch |
| Simulator model | The same local model for now, configurable (`EVAL_SIMULATOR_MODEL`), checked on dev for staying in role and revealing hidden facts only when asked | One local model; a stronger adversarial player is a settings change |

## Decisions taken during implementation (session 14a)

| Question | Decision | Why |
|---|---|---|
| How does a script follow system-specific questions? | The scripted driver answers, the same way for every system, what a real customer would: the language question, the workflow question (with the scenario's workflow), a switch question (yes), the dispute reason, and the protective block offer; answers to a clarifying question are marked `when_asked` (scenario 1.4.0) and sent only when asked | Without this, a script written for one system's flow would test the script, not the system |
| A `tool_failure` scenario for the unavailable risk estimator has no tool to fail | The scenario contract (1.4.0) accepts a `model_unavailable` fixture instead of a tool failure plan | The prompt asks for the estimator being unavailable under tool failure |
| Learned router and resolver defaults | Keep `keyword@1` and `rules@1`: on dev with no model, P's safe automated resolution is 71/112 with the baselines and 80/112 with `tfidf@champion` and `lgbm@champion` (78/112 and 76/112 with the router alone), with overlapping Wilson intervals; 14b repeats the comparison with the local model before the test run (BACKLOG) | The plan's rule: change a default only on a gain the intervals support |
| Learned risk estimator default | Keep `score_band@1`: on the dev credit scenarios `logreg@champion` changes nothing (19/28 either way), and with it every first-time applicant goes to review (ADR 0030) | No measured gain; the baseline gives first-time applicants an estimate |
| First-time applicants under a learned estimator | Keep sending them to human review (band `unknown`), as built | Out of the estimator's training population; review is the safe outcome |
| The evaluation world | 39 synthetic customers (13 roles in 3 countries), each case on a fresh copy | Deterministic, CI-able, and no organizer data in git |

## Decisions taken during session 14b

| Question | Decision | Why |
|---|---|---|
| Where does the test run execute? | From a separate git worktree detached at the run's commit (`6bc2e9d`); the judge and `publish` run there too, and the published files are copied into `main` and checked byte for byte | Work on `main` continued during the three-hour run; a pinned checkout keeps the code and the manifest's commit the same |
| Judge sample size | 100 transcripts in all (B0 40, P 30, B1 30), what `bank-eval judge --sample 100` draws; the feasibility table's 100 per system is BACKLOG | The command's stratified sampler spans the systems; the judge is unvalidated either way until the human ratings exist |
| Unsafe outcomes that are grader false positives or simulator artifacts on review | Published as graded, with each case explained in `results.md`; the grader and harness fixes are 14c rows measured on dev | Changing a grader after reading test transcripts and regrading would tune the measurement on test |
| Between-run variance | Read on the 48-scenario subset alone in the analysis; the generated column mixes run 1's full split with the subset (BACKLOG) | The plan defines the variance over the repeated scenarios |
| Test cassettes | Copied into `main` uncommitted, like the dev ones, until pending action 42 is decided; the judge's recordings sit in `evals/cassettes/eval/test-judge/` | The fixture cassette checks read `evals/cassettes/runs/` and skip `evals/cassettes/eval/` |
| Learned router, resolver, and risk estimator defaults | Keep `keyword@1`, `rules@1`, and `score_band@1`: on dev with the local model the learned pair resolves 75/112 against 74/112 (overlapping intervals, routing scenarios 6/10 either way), and `logreg@champion` resolves 20/28 like the baseline while answering two review cases as indicatively eligible | The plan's rule (a gain with non-overlapping intervals on dev); the comparison ran after the test run and used nothing from it |
