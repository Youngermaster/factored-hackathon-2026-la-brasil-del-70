# Submission package

| Document | Purpose |
|---|---|
| [SUBMISSION.md](SUBMISSION.md) | The checklist that follows the brief's submission requirements: what is done, and the human steps in order (deploy, fill `deploy.url`, export the slides, record the video, make the repository public, send the email) |
| [brief-traceability.md](brief-traceability.md) | Every requirement of the brief mapped to where it is implemented, where it is proven, and its status, with one column per workflow |
| [LOCAL-RUN.md](LOCAL-RUN.md) | A verified, step-by-step local walkthrough: the dev stack with the fake and the local model, what to check in the browser, the evaluation report, the production stack in local TLS mode, the slides, the gates, troubleshooting, and the verification log |
| [email-draft.md](email-draft.md) | The draft email to `hackathon.admin@factored.ai`; never sent by a session |

`make submission-check` (`scripts/submission_check.sh`) runs `make check`, `make security`, `make eval-smoke`, the slides' `pnpm verify`, and `make docs-check`, prints a pass or fail line per gate, and then lists the human steps that remain. It never deploys, pushes, sends, or reads `.env`.

The slides, the narration, and the video guide live in [slides/](../../slides/README.md); the video's timed shot list in [docs/demo/video-plan.md](../demo/video-plan.md), its narration by speaker in [docs/demo/video-monologue.md](../demo/video-monologue.md), and the full demo walkthrough in [docs/demo/script.md](../demo/script.md). Screenshots for review are produced on demand by `node tooling/screenshots.mjs`, run from `apps/web/` against a running stack (into the gitignored `apps/web/.shots/`), because they change with every copy or design change.
