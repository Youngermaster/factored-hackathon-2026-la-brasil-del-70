# bank-evals: evaluation harness

## Responsibility

`bank-evals` measures the system against baselines on the same held-out workload, using the outcome definitions from the brief: safe automated resolution, containment, escalation quality, unsafe outcomes, and operating efficiency. It owns:

- the scenario set (332 test, 122 dev) in Spanish and Portuguese, its generator, lint, leakage guards, and the test set lock;
- the synthetic evaluation world every case starts from;
- the systems under test: H (historical reference), B0 (menu bot), B1 (naive agent), P (the proposed system in process);
- the scripted and simulated customers, the deterministic graders, the judge, the metrics and statistics, and the reports and published summaries;
- the retrieval evaluation of phase 07.

Offline measurements, simulations, and projected figures are always labeled separately. The harness is separate from the test suite and runs through `make eval`. The design is in [docs/evaluation/](../docs/evaluation/README.md).

## Layout

| Path | Content |
|---|---|
| `src/bank_evals/scenarios/` | `model.py` (the contract, `scenario.v1.json` 1.4.0), `family_data/*.yaml` (situations and phrasings), `families.py`, `facts.py`, `generate.py`, `mix.py`, `lint.py`, `leakage.py`, `store.py` (files and lock), `translate.py` (pt proposals, pending review) |
| `src/bank_evals/world/` | The synthetic world (`build.py`, `records.py`), symbolic references (`model.py`), record fixtures (`fixtures.py`) |
| `src/bank_evals/systems/` | `base.py` (the `SystemUnderTest` interface and the transcript), `engine_system.py` (P and B0), `naive_agent/` (B1 and its database), `historical.py` (H), `failures.py` and `schedule.py` (scheduled tool failures), `views.py` |
| `src/bank_evals/users/` | `scripted.py` and `simulated.py` drivers |
| `src/bank_evals/graders/` | `grade.py` and the state, disclosure, action, and lexicon modules; `model.py` (`CaseGrade`, `CaseResult`) |
| `src/bank_evals/metrics/` | `stats.py` (Wilson, Clopper-Pearson, zero-event bounds, pass^k), `aggregate.py`, `compute.py` |
| `src/bank_evals/runner/` | `run.py`, `cases.py`, `llm.py` (off, replay, record, inject), `fake.py` (the smoke client), `wiring.py`, `subset.py`, `estimate.py` |
| `src/bank_evals/reports/` | `summary.py` (`EvaluationSummary` 1.1.0), `markdown.py`, `tables.py` |
| `src/bank_evals/judge.py` | The judge, the stratified sample, and Cohen's kappa |
| `src/bank_evals/prompts/` | Evaluation prompts: `naive_agent_step`, `simulate_customer`, `judge_transcript`, `translate_to_portuguese`, and their output models |
| `src/bank_evals/commands/` | The `bank-eval` commands |
| `src/bank_evals/retrieval/`, `language_checks.py` | Phase 07 retrieval evaluation; lexical language checks |
| `data/` | `scenarios.dev.jsonl`, `scenarios.test.jsonl`, `test_set.lock`, the retrieval judgments, and the recorded hosted embeddings for them |
| `cassettes/` | `eval/<split>/` recordings of evaluation runs (session 14b) and the phase 08 fixtures ([README](cassettes/README.md)) |
| `tests/unit/`, `tests/integration/`, `tests/support/` | Unit tests, the smoke suite end to end, and shared test support |

`bank-evals` depends on `bank-agent` for the domain vocabulary and to run P and B0 through the composition root's builders. Import-linter contracts guarantee that `bank_agent` never imports `bank_evals`, and that B1 (`bank_evals.systems.naive_agent`) never imports the policy kernel, the application layer, the adapters, the bootstrap, or the API.

## Public interfaces

The `bank-eval` command:

| Command | What it does |
|---|---|
| `scenarios generate`, `scenarios check` | Generate both splits from the seed (refusing to change the locked test split without `--relock`); lint, leakage guards, and the lock |
| `run` | Play and grade scenarios for `--systems b0,p,b1` with `--llm off`, `replay`, `record`, or `fake`; `--runs N --repeat subset` (or `all`), `--workflow`, `--scenario`, `--smoke`, `--set WORKFLOW_ROUTER=...`, `--resume`, `--mlflow`; writes `reports/eval/<run_id>/` (gitignored) |
| `report`, `compare` | Regenerate `report.md` from the results; compare runs |
| `estimate` | Project calls, wall clock, and cost from a measured run |
| `judge` | Rate a stratified sample; with `--ratings`, the agreement with human ratings |
| `publish` | Summaries for `/v1/eval/summaries`, `docs/evaluation/results.md` and `failures.md`, and the run's metrics |
| `retrieval` | The retrieval evaluation: BM25, e5 dense and hybrid (with the `ml` extra), Qdrant and Qdrant hybrid (from the committed recording of hosted embeddings; `--record-embeddings` re-records on the evaluation account) |

## How to extend

- **New situation:** add it to the workflow's `family_data/<workflow>.yaml` with at least two phrasings (one can go to dev), labels from the policy documents, and facts in braces from `scenarios/facts.py`; run `make eval-scenarios` (a changed test split needs `--relock`, recorded in the phase log with the reason).
- **New persona role or record:** add it in `world/records.py` and name it symbolically; never copy organizer records.
- **New scenario field:** add it to `Scenario` as an optional field marked `AddedIn`, run `make contracts`, and add the changelog row.
- **New system under test:** implement `SystemUnderTest` (`start` returns a `CaseSession`), return turns as `TurnView`, and register it in `runner/run.py`.
- **New grader:** add a check in `graders/`, record findings with `ctx.fail` and unsafe events with `ctx.flag_unsafe`, and extend `ROOT_CAUSE_ORDER` if it is a new root cause class.
- **New evaluation prompt:** add `prompts/<id>/<version>.md` with an output model in `prompts/outputs.py`.

## How to test

```bash
uv run pytest evals/tests -m unit
uv run pytest evals/tests/integration -m integration
make eval-smoke
```

Coverage for `evals/src` is gated at 80% line coverage by `make check`.
