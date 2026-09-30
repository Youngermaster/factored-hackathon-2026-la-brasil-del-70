# Phase 17 plan: documentation completion and final audit

Not a plan-mode phase. The human delegated approvals to the orchestrator, so this plan is committed first and every open question is decided below by the most defensible option, with its reasoning. The pull (`git pull --ff-only`) succeeded: `main` was already up to date at `28b143b`.

Human decisions given to the session (2026-09-30):

- **License: none.** The README states "All rights reserved"; no LICENSE file is added.
- **Organizer data-use terms:** the human confirmed that no restriction is known, so the committed pseudonymized sample stays. The confirmation and the reasoning are recorded in `docs/data/data-use.md`; pending action 2 and the BACKLOG row close.
- **The teammate branch `feat/privacy-safe-langfuse-api` stays unmerged.** ADR 0025's scope is not followed; no Langfuse work.
- **Deployment host: undecided.** `deploy.url` stays pending in `slides/data/metrics.yml`; the submission checklist makes deploying and filling it an explicit human step before the final export.
- **Evaluation model:** the published results are the local `qwen2.5:7b-instruct` run; a hosted rerun is optional future work. Every claim quotes `docs/evaluation/results.md` exactly, with its label (simulation, offline, projection).

## Scope as adapted by the orchestrator

The kit prompt lists more than the orchestrator's scope. The orchestrator's seven items come first; kit items outside them are done when small and useful to a judge, otherwise mapped to what already exists (decision 8).

1. Root `README.md` rewritten for judges.
2. Documentation hygiene: `docs/README.md`, `docs/adr/README.md`, stale statements in package READMEs and model cards, `AGENTS.md` current state, ADR 0000 handled neutrally (pending action 14), Markdown and Mermaid valid.
3. Brief traceability matrix: `docs/submission/brief-traceability.md` (the kit's path).
4. The demo finding: the seeded open dispute case, plus a drive of every demo-guide message through the API with the fake model.
5. Submission package in `docs/submission/`: checklist, a draft email (never sent), and `make submission-check`.
6. Slides and video: `slides/script.md`, `slides/VIDEO.md`, `docs/demo/script.md` checked against the final system; `pnpm verify` and `pnpm check:fit` pass with only `deploy.url` pending.
7. Final audit: the gates, the PROGRESS entry, and every open human action with an owner suggestion.

## Files to create or change

| Area | Files |
|---|---|
| Demo fix | `data_platform/src/bank_data/seed/{bundle,runner,command}.py`, `data_platform/tests/integration/test_seed.py`, a new API-level regression test, `apps/web/src/features/demo-guide/model/scenarios.ts`, the demo guide copy in `apps/web/src/shared/i18n/locales/{es,pt,en}.json`, `docs/demo/{personas,script}.md` |
| Data use and license | `docs/data/data-use.md` (new), `docs/data/data-card.md`, `README.md`, `docs/PROGRESS.md` (actions 1 and 2), `docs/BACKLOG.md` |
| Judge-facing docs | `README.md`, `LIMITATIONS.md` (new), `docs/architecture/overview.md` (final context, container, component views and a turn sequence), `docs/workflows/README.md` (new), `docs/security/README.md` (new) |
| Hygiene | `docs/README.md`, `docs/adr/README.md`, `AGENTS.md`, `services/api/src/bank_agent/adapters/README.md`, `contracts/README.md`, the model cards and `docs/workflows/workflow-router.md` (defaults decided in 14b), `CONTRIBUTING.md` |
| Submission | `docs/submission/{README,SUBMISSION,brief-traceability,email-draft}.md`, `scripts/submission_check.sh`, `Makefile` (`submission-check`) |
| Slides | `slides/script.md`, `slides/VIDEO.md`, `slides/locales/en.yml` (close slide), `slides/README.md` |
| Closing | `docs/BACKLOG.md` (every phase 17 row resolved or re-owned), `docs/PROGRESS.md` (phase 17 entry and current state) |

## Tests to add

- Seed: the seeded case opens at the seeding instant with the policy SLA from there (fixed instant, unit of the bundle), and the seed test keeps its idempotence.
- Regression: a status question about the freshly seeded case answers with the case and its deadline (`dispute.status_one`, outcome resolved), not an overdue escalation, driven through the ASGI app on PostgreSQL.
- Web: the demo guide lists the new dispute scenarios (existing test file).
- `scripts/submission_check.sh` passes shellcheck (it runs in `make security`).

## Decisions

1. **The seeded dispute case opens at the seeding instant, not one day after the purchase.** The live system opens every case on the wall clock (`application/tools/writes.py`: `sla_due_at = at + SLA`) while dispute windows are evaluated against the data as-of date (`POLICY_DATA_AS_OF`). The seed now opens its case exactly as the system would open it today, so its SLA (45 days in MX) is live for the demo and the status question answers with the deadline. The alternative of comparing the SLA with the data as-of date in the status handler would change engine behavior for real cases (a case opened today would never breach), and the alternative of opening a fresh case first fails because any breached open case of the customer still escalates. Re-running the seed does not move an existing case (inserted only when missing), so a demo is recorded on a fresh volume, as the demo script already says.
2. **The demo guide's dispute paths.** `dsp-mx-open-case` becomes the normal "status with the deadline" path (matching `docs/demo/personas.md`). The escalation path moves to `dsp-ar-repeat-complainer` (the persona built for it), with the exact messages that route as described when driven through the API; if it does not route, the next candidate is an amount above the automatic limit. The SLA-breach escalation stays proven by tests and the evaluation (`DSP.case_within_sla`).
3. **The drive of the demo guide** runs against a throwaway compose project (`bank-agent-p17`, its own volume and port), never the developer's database: migrate, seed from the committed sample, run the API with `DEMO_MODE=true` and `LLM_PROVIDER=fake`, then every scenario in es and pt through HTTP. The project is removed afterwards.
4. **License wording:** "All rights reserved" with no LICENSE file, as the human decided; the README says the repository is public for judging only.
5. **Data-use record:** `docs/data/data-use.md` records the human's confirmation (2026-09-30) and the reasoning (synthetic organizer data, pseudonymized direct identifiers, bounded at 2,595 rows, reproducible by `make data-sample`), plus the guard re-run (`scripts/checks/check_data_sample.py`) and a README-to-files check.
6. **ADR 0000 (pending action 14):** listed in the ADR index with its own status (Proposed) and a neutral note that it is the team's alignment record merged from the team repository, with statements not recorded elsewhere. The record is not edited; the action stays with the team to accept or leave as proposed. ADR 0025 to 0028 keep their authors' statuses, with a note that the build does not follow 0025's scope and that 0026 to 0028 describe future directions not built.
7. **ADRs are not rewritten.** Where an ADR says "until phase 14", the model cards and workflow pages carry the 14b decision, and the ADR index notes the outcome; no ADR text changes.
8. **Kit items mapped to existing artifacts:** the slide outline is the Slidev deck (`slides/`), the video script is `slides/script.md` with `slides/VIDEO.md` and `docs/demo/script.md`, screenshots are captured by `apps/web/tooling/screenshots.mjs` (a documented manual step; the PNGs stay out of git because they are regenerated per run), and the extension guides are AGENTS.md section 7 (linked from CONTRIBUTING.md). The ADR consistency table and the missing workflow pages (evaluation harness, deployment) are written only if time allows after the orchestrator's items; otherwise they are BACKLOG rows.
9. **Evaluation freshness:** since the run commit `6bc2e9d`, prompts, policies, the price table, and `evals/` are unchanged; the engine changed in phases 15 and 16 (telemetry, the degradation ladder, one clarification line, the eligibility assessment limit, the agent credit moves). No rerun (the published run stays the evidence); the README states the difference and `make eval-smoke` runs on the current code.
10. **Fresh clone check:** a clone into the scratch directory with only `.env` from `.env.example`, then `uv run --frozen` for the pipeline from the committed sample and `make eval-smoke`. `make up` in a clone would share the compose project name and volume with the developer's stack, so the clone's database path is the throwaway project of decision 3.
11. **`make submission-check`** runs `make check`, `make security`, `make eval-smoke`, the slides `pnpm verify`, and `make docs-check`, then prints the remaining human steps. It never deploys, pushes, sends, or reads `.env`.

## Risks

- `make check` takes more than ten minutes; it runs in the background and is polled.
- The demo guide change touches web tests and copy in three locales; the locale parity and hard-coded string tests guard it.
- Slides `check:fit` needs the dev server on port 3131; the close slide copy change must still fit.

## Open questions

None block correctness. The host, the video, the public flip, and the email are human steps listed in the checklist.
