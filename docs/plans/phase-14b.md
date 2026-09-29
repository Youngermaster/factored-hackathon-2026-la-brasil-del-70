# Phase 14, session 14b: the live local runs

Session 14a built the harness ([phase-14a.md](phase-14a.md)). Session 14b runs it live on the local model and publishes the numbers, following the run protocol of [the evaluation plan](../evaluation/plan.md#run-protocol-the-local-model-14b) and the metric definitions of [methodology.md](../evaluation/methodology.md). The pull at the start was a fast-forward no-op ("Already up to date").

Session 14b has two parts:

1. **Fixes and the dev run** (this plan's first part): the three P fixes 14a left, a full live run on the dev split with cassettes, and the projection for the test run. Every choice here uses dev only; the test split is not read.
2. **The test run** (run by the orchestrator afterwards): P, B0, and B1 on the frozen test split, the variance runs on the stratified subset, the judge, and publication.

## Part 1: the three fixes (from the 14a BACKLOG)

Each keeps the design thesis: the model understands, deterministic code decides. Each has unit tests and workflow integration tests on the in-memory adapters and PostgreSQL.

| Row | Fix | Where |
|---|---|---|
| Third-party requests phrased product first ("la tarjeta de crédito de mi mamá", "o cartão de crédito da minha mãe", "em nome do meu pai", "apoderado de Rafael") | The keyword signal allows up to three qualifier words from a closed list between the product and a relative or other owner, reads "dele" and "dela" after a product, "em nome do/da", and representation words ("apoderado", "procurador"). A purchase or a charge keeps the owner right after the noun, so "la compra de los útiles de mi hijo" stays the customer's own. The kernel then refuses with `PRV-ALL-2` before any tool runs | `bank_agent.application.engine.signals` |
| The local model read "Sí, quiero solicitarlo" as a request for a person, so P escalated an intake | A plain yes or no (six words or fewer that parse as yes or no) while a question is pending (a state that awaits an answer, or the engine's switch question) is resolved by the deterministic parsers alone: the gate does not ask the model for escalation signals on it. The keyword signals still run, so "sim, quero falar com um atendente" escalates; a longer turn at the same step still reaches the model. The prompt is unchanged, and a confirmation turn costs one model call less | `bank_agent.application.engine.gate` |
| B1 wrote "estás calificado" and the approval list missed it | The approval lexicon shared by the pack loader, the eligibility renderer, the grounding verifier, and the credit-safety grader gains qualification stems (es "calificad", "cualificad", "precalific"; pt "qualificad", "pré-qualific"; en "qualified", "prequalif") and word-bounded phrases ("calificas para", "você se qualifica para", "habilitado para el préstamo", "seu crédito foi liberado", "you qualify for"). "Pre-aprobado", "aprovado", and "elegível para aprovação" were already caught by the stems. Every engine template, clause, and eligibility message still passes | `bank_agent.policy.lexicon` |

## Part 1: the dev run protocol

Settings, for every live command in this session (the local model through Ollama; nothing hard-codes a provider):

```bash
export LLM_PROVIDER=litellm LLM_PRIMARY_MODEL=ollama/qwen2.5:7b-instruct LLM_API_BASE=http://localhost:11434
export LLM_TIMEOUT_SECONDS=120 LLM_SESSION_TOKEN_LIMIT=1000000
```

- `LLM_SESSION_TOKEN_LIMIT=1000000` lifts the per-session token cap that protects the API; an evaluation run plays hundreds of conversations in one process. `LLM_TIMEOUT_SECONDS=120` covers the slowest local calls (B1's prompt carries the policy).
- Ollama must be serving `qwen2.5:7b-instruct` at `http://localhost:11434` (`curl -s localhost:11434/api/tags`). Keep the machine awake (on macOS, `caffeinate -i` around the run) and run nothing else heavy on it, so the latency numbers are not distorted.

```bash
uv run --frozen --extra litellm bank-eval run --run-id dev-local --split dev --llm record --mlflow
uv run --frozen bank-eval estimate reports/eval/dev-local
```

- The run plays all 122 dev scenarios with B0, P, and B1 (366 cases), the simulated customer on the 20 simulated dev scenarios, and records every model call into `evals/cassettes/eval/dev/`. It is a local development run on `qwen2.5:7b-instruct`, labeled as such everywhere; its numbers are never the published results.
- Clear, deterministic, and cheap P bugs found on the dev run are fixed with regression tests; anything else goes to BACKLOG. Nothing is tuned on the test split.
- The estimate uses the dev run's measured calls per case and latency per call. If the test run projects above 6 hours, the plan's levers apply in order (judge on the 100-transcript sample, which is the default; then the simulated subset shrinks to the direct injections plus half of the ambiguous scenarios; then P's output token cap), and the run records which were used.

## Part 2: the test run protocol (run by the orchestrator)

Same settings as above. The scenario check first (lint, leakage, and the test set lock must pass):

```bash
uv run --frozen bank-eval scenarios check
uv run --frozen --extra litellm bank-eval run --run-id test-local --split test --llm record --runs 3 --repeat subset --mlflow
```

- Run 1 plays the full test split (332 scenarios) with B0, P, and B1; runs 2 and 3 play the stratified 48-scenario subset with every system (pass^3 and the between-run variance; B0's repeats must be identical). Cassettes go to `evals/cassettes/eval/test/`.
- **Interrupted?** Rerun the same command with `--resume`: cases already in `reports/eval/test-local/results.jsonl` are skipped (their cassettes stay), and the remaining cases are played live. Record mode always calls the model and overwrites a cassette with the same key, so never rerun without `--resume` on a directory that holds finished cases.

```bash
uv run --frozen --extra litellm bank-eval run --run-id test-local --split test --llm record --runs 3 --repeat subset --mlflow --resume
```

- Then the judge (tone and clarity only, a stratified 100-transcript sample per scored system), the report, and publication:

```bash
uv run --frozen --extra litellm bank-eval judge reports/eval/test-local --llm record --sample 100
uv run --frozen bank-eval report reports/eval/test-local
uv run --frozen bank-eval publish reports/eval/test-local
```

- `publish` refuses a run with cassette coverage below 100% unless `--allow-partial`, which adds a note. Every published number carries the model and provider label (`ollama/qwen2.5:7b-instruct (litellm)`); P and B1 numbers are simulated-scenario results on a synthetic world, not production outcomes.
- Cassettes and `reports/eval/` raw outputs are not committed: `reports/eval/` is ignored, and whether `evals/cassettes/eval/` is committed is pending human action 42 (its measured size is recorded in the phase log).

## Files

| Area | Files |
|---|---|
| Fixes | `services/api/src/bank_agent/application/engine/signals.py`, `gate.py`, `services/api/src/bank_agent/policy/lexicon.py` |
| Tests | `services/api/tests/unit/application/engine/test_signals_phase14b.py`, `services/api/tests/unit/policy/test_approval_lexicon.py`, `services/api/tests/unit/application/grounding/test_verifier_claims.py`, `services/api/tests/integration/workflows/test_third_party_requests.py`, `test_pending_answer_signals.py`, `evals/tests/unit/harness/test_graders_content.py` |
| Docs | this plan, `docs/PROGRESS.md`, `docs/BACKLOG.md` |
