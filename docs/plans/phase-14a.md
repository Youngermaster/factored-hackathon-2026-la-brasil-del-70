# Phase 14, session 14a: the evaluation harness

The prompt (`kit/prompts/14-evaluation.md`) asks for plan mode. The human delegated plan approval to the orchestrator and wants the MVP first, so the plan is committed first and implementation follows immediately; every open question is decided by the session under the orchestrator's pre-approval ([evaluation plan](../evaluation/plan.md#decisions-on-open-questions-decided-by-the-session-under-the-orchestrators-pre-approval)). The pull at the start was a fast-forward no-op ("Already up to date").

Session 14a builds everything except the live model runs and the published numbers, which are session 14b. Only `FakeLLM`, the refusing client, and cassettes run in tests and CI. A few live calls to the local Ollama model measure latency and check the simulator, judge, and B1 prompts.

## Files to create or change

| Area | Files |
|---|---|
| Plan and docs | `docs/evaluation/plan.md`, `methodology.md`, `judge-rubric.md`, `README.md` (Mermaid harness diagram, commands), generated `results.md` and `failures.md` (from dev runs in 14a, labeled; test in 14b) |
| Scenario contract | `bank_evals.scenarios.model` (additive 1.4.0: `scripted_fallback`, `template_family`, `ambiguity` tags stay in `tags`), `contracts/schemas/scenario.v1.json`, `contracts/README.md` changelog |
| World | `bank_evals.world`: personas and records (synthetic, seeded), symbolic record references, fixtures applied per case |
| Generators | `bank_evals.scenarios.generate` (families per workflow and category, dialect rendering, split quotas, seed), `templates/` per workflow, `security.py` (exact attack strings in es, pt, en), `translate.py` (cassette-backed pt helper, `pending_review`), `lint.py` (mix, languages, workflow on in-scope), `leakage.py`, `lock.py`; `evals/data/scenarios/{dev,test}.jsonl`, `evals/data/test_set.lock` |
| User drivers | `bank_evals.users`: scripted driver, simulated driver (prompt `simulate_customer@1`) |
| Systems | `bank_evals.systems`: `base.py` (interface, transcript), `proposed.py` (P and B0 on the engine), `naive_agent/` (B1, its database, tools, prompt `naive_agent_step@1`), `historical.py` (H) |
| Graders | `bank_evals.graders`: outcome, state, tool audit and verification, disclosures, handoff, routing, account data, credit safety, language; `judge.py` (prompt `judge_transcript@1`), judge sample export and agreement |
| Metrics | `bank_evals.metrics`: Wilson, Clopper-Pearson, zero-event bounds, pass^k, between-run variance, per-workflow and slice aggregation, disparities, latency and cost |
| Runner and reports | `bank_evals.runner` (cases, runs, LLM modes, cassette coverage, estimate), `bank_evals.reports` (`results.jsonl`, `metrics.json`, `report.md`, `results.md`, `failures.md`, summary 1.1.0), MLflow logging |
| CLI and make | `bank-eval` commands `run`, `compare`, `report`, `publish`, `estimate`, and `scenarios`; `make eval`, `make eval-test`, `make eval-smoke`; CI smoke job |
| Engine fixes (BACKLOG, phase 14) | card status phrasing with "bloqueado/bloqueada"; "Aprove o meu crédito agora"; a plain "sí"/"sim" accepting the offer of a person |
| Boundaries | `pyproject.toml`: `bank_evals` as a root package, contracts that `bank_agent` never imports `bank_evals` and that B1 never imports the kernel, application, or persistence adapters |
| Prompt registry | `parse_prompt_file` and `FilePromptRegistry.from_directory` accept an output model table, so evaluation prompts load with evaluation output models without entering `bank_agent.domain` |

## Tests to add

- Unit: every metric function (Wilson and Clopper-Pearson against known values, zero-event bounds, "not defined", pass^k, variance), each grader on synthetic transcripts (positive and negative), scenario schema validation, the generator lint, generator determinism (same seed, same bytes), the test set lock check, the leakage guards, the scripted and simulated drivers with `FakeLLM`, B1's loop and tools with `FakeLLM`, the judge parser, the report writers, the summary against `EvaluationSummary` 1.1.0, the CLI.
- Integration: the 12-scenario smoke suite runs all four system types end to end (H as the reference loader) with `FakeLLM` and the fixture cassettes; `bank-eval run` writes the three outputs; `publish` writes a summary the API adapter reads.
- Regression tests for the three engine fixes, on both backends.

## Risks

- **Label errors.** Expected outcomes are written from the policy docs; a wrong label looks like a system failure. Mitigation: every label comes from shared expectation rules, dev runs are read case by case, and label fixes are made on dev only and recorded.
- **Local model quality.** A 7B model may break B1's JSON loop or play the simulated user poorly. Mitigation: bounded steps, one repair by the gateway, invalid output counted as a B1 failure (not a harness error), simulator checks on dev, the model label on every number.
- **Wall clock.** The projection may exceed 6 hours. Mitigation: the ordered levers in the plan, measured on dev first.
- **Coverage gate** (80% for `evals/src`): the harness is large; tests are written with each module.
- **Evaluation world realism.** Synthetic records are cleaner than production data. Stated as a limitation; the missing and incorrect data category exercises gaps.

## Open questions

None blocking. All are decided in the [evaluation plan](../evaluation/plan.md#decisions-on-open-questions-decided-by-the-session-under-the-orchestrators-pre-approval). Pending human actions (not blockers): the 100 judge-validation ratings, the native review of the Portuguese scenarios, and the review of a sample of generated scenarios per workflow.
