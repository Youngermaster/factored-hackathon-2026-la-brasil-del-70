# Submission checklist

The organizer's published challenge window ends **2026-10-05** ([brief](../organizer/BRIEF.md#submission-requirements)); no cutoff time or timezone is stated here. The team set a separate **internal MVP completion window ending Sunday, 2026-10-04**, leaving one calendar day of buffer. This is a target, not a completion claim. Submission requires a public repository named `factored-hackathon-2026-[team name]`, a link to the deployed tool, a 4 to 6 slide presentation, and a video pitch, sent to `hackathon.admin@factored.ai`.

Everything automated is done and checked by `make submission-check`. The unchecked boxes below are human steps, in the order they depend on each other. No session deploys, pushes, publishes, or sends anything.

## Done in the repository (phase 17)

- [x] The repository is named `factored-hackathon-2026-la-brasil-del-70` (the team is La Brasil del 70).
- [x] License decided: none; the README states "All rights reserved" (human decision, 2026-09-30).
- [x] Organizer data-use terms checked for the committed sample in `data_platform/sample/`: the human confirmed on 2026-09-30 that no restriction is known; the record and the guard re-run are in [data-use.md](../data/data-use.md).
- [x] The README, [LIMITATIONS.md](../../LIMITATIONS.md), the [brief traceability matrix](brief-traceability.md), and the documentation index are final; every evaluation number quotes [results.md](../evaluation/results.md) with its label.
- [x] The deck has six main slides plus one appendix ([slides/README.md](../../slides/README.md)); every number comes from `slides/data/metrics.yml` with its kind and source, and only `deploy.url` is pending.
- [x] The demo guide and the demo script were driven through the API on a fresh seed of the committed sample, in es and pt ([demo script](../demo/script.md)).
- [x] The production stack is built and verified locally with TLS ([deploy/README.md](../../deploy/README.md), phase 16 entry in PROGRESS).

## Human steps, in order

1. [ ] **Run the gates on the commit to submit.** `make submission-check` from a clean `main`: `make check`, `make security`, `make eval-smoke`, the slides' `pnpm verify`, and `make docs-check` all pass; it then lists what is left. Owner: the technical lead.
2. [ ] **Choose the host and deploy** following [deploy/README.md](../../deploy/README.md) (Lightsail 4 GB recommended): the VM, the firewall, DNS, the server env file (filled on the server only), `deploy/prod.sh check`, `build`, `up`, `seed` on a fresh volume, `smoke`. Choose the model (the fake provider, a hosted provider with a spending limit, or the `ollama` profile) and, for a hosted one, verify its price entry and data controls first (pending actions 7 and 45). Owner: the technical lead.
3. [ ] **Verify the deployment from a laptop:** `make smoke SMOKE_URL=https://<host>` and `make csp-check SMOKE_URL=https://<host>`; open `/demo` and play one scenario per workflow. Set up the uptime monitor, the daily backup, and the daily smoke test from the guide.
4. [ ] **Fill the deployed URL** in `slides/data/metrics.yml`, replacing the pending line with, for example, `deploy.url: {value: "https://<host>", display: "<host>", kind: offline, source: deploy/README.md}`, and in the README's link table ("Deployed demo"). Commit.
5. [ ] **Export the slides** (Node 24, from `slides/`): `pnpm verify`, then `pnpm dev` and `pnpm check:fit` in a second terminal, then `pnpm export:final` (it fails while any metric is pending). The PDF lands in `slides/export/`. Send the six main slides; drop the appendix pages or keep them as a labeled extra.
6. [ ] **Record the video** against the deployed URL right after a fresh seed: the shot list and timing in [slides/VIDEO.md](../../slides/VIDEO.md), the narration in [slides/script.md](../../slides/script.md), and the live scenes and exact inputs in [docs/demo/script.md](../demo/script.md). About 3:30 to 4:00, captions on, exported as `la-brasil-del-70-pitch.mp4`. Upload it where the organizers can play it without an account (for example an unlisted video) and put the link in the README. Owner suggestion: one narrator for the whole video; Miguel Correa or the technical lead.
7. [ ] **Push `main` and make the repository public** on GitHub. Before flipping: `make security` is clean (gitleaks over the full history), and the name is exactly `factored-hackathon-2026-la-brasil-del-70`.
8. [ ] **Send the email** from [email-draft.md](email-draft.md) to `hackathon.admin@factored.ai` before 2026-10-05, with the repository link, the deployed URL, the PDF attached or linked, and the video link. Owner suggestion: Miguel Correa (project manager).
9. [ ] **Keep the demo running until 2026-10-16**, then `deploy/prod.sh destroy --yes` and release the DNS record, the static IP, the VM and its disks, and any provider key ([deploy/README.md](../../deploy/README.md), "Take the demo down").

## Human reviews still open

These do not block the submission; the documents state each as a limitation until it is done. The full list with owners is the "Pending human actions" list in [PROGRESS.md](../PROGRESS.md) and the phase 17 entry there.
