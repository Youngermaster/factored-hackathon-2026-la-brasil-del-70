# Organizer data-use terms and the committed sample

This page records the check CLAUDE.md rule 5 requires before the repository is made public: that the organizer's data-use terms allow the bounded sample committed in [`data_platform/sample/`](../../data_platform/sample/README.md). It closes pending human action 2 in [PROGRESS.md](../PROGRESS.md) and the matching BACKLOG row. Which fields reach a model provider is a separate question, answered in [security/data-use.md](../security/data-use.md).

## Decision

The committed sample stays in the repository when it becomes public.

- **Human confirmation, 2026-09-30.** The human who owns the repository and drives the build confirmed that no restriction on redistributing this sample is known. The organizer material available to the team (the problem statement, the kickoff deck, and the data dictionary; [brief summary](../organizer/BRIEF.md)) contains no redistribution clause for the synthetic dataset.
- **Recorded by** the phase 17 session, under the human's delegated approval ([phase 17 plan](../plans/phase-17.md), decision 5).

## Reasoning

| Point | Evidence |
|---|---|
| The data is synthetic | The organizer describes the dataset as a fully synthetic bank (LATAM Bank) generated for the event; it holds no real customer. The brief asks teams to label inputs as real, de-identified, synthetic, or team-generated ([data card](data-card.md)) |
| Direct identifiers are pseudonymized anyway | Document numbers, first and last names, emails, phones, addresses, and birth dates are replaced with deterministic, format-valid pseudonyms, so the data contracts still pass and no identifier is copied verbatim (the treatments table in the sample README; `data_platform/src/bank_data/sample/pseudonyms.py` and its tests) |
| It is bounded | 2,595 rows across all tables: 2,470 in the ingested files and 125 in `preview/`, against a limit of 5,000, and no table is complete (for example 255 of 350 branches, 74 of 150,000 customers). `scripts/checks/check_data_sample.py` fails `make check` above the limit or when the README counts differ from the files |
| It is reproducible and not hand-picked | `make data-sample` regenerates it from the pipeline: customers chosen by a seeded hash and followed through every table, with the delivery version (`organizer-v1.0.0-2026-08-31`, snapshot 2026-06-17) and the manifest etags stated in its README |
| It carries nothing restricted | No credentials, `.env` values, or text from the data dictionary PDF; gitleaks scans the full history in `make check` and `make security` |
| It serves the judges | `make pipeline` and `make seed` run from it offline with no credentials, which is how a judge reproduces the data platform and the demo, and what the deployed demo is seeded from |

## Checks re-run for this record (2026-09-30)

- `uv run --no-project --python 3.12 python scripts/checks/check_data_sample.py`: "sample within bounds and documented" (the README's per-table counts equal the files').
- The README states the source, the dataset version, the extraction command, the query and seed, the row count per table, the column treatments, and the organizer-data notice, as rule 5 lists.
- The API and the evaluation harness never send sample identifiers to a model provider ([security/data-use.md](../security/data-use.md)).

## What would change the decision

- If the organizer publishes data-use terms that forbid redistribution, or someone from the organizers asks, the team stops and asks the human before anything else. The sample is removed from the history only on the human's explicit instruction; no session rewrites history on its own.
- A new sample (`make data-sample`) must pass the same guard and get its README regenerated; this record then needs a line for the new version.

## Residual risk

The confirmation is the human's statement that no restriction is known; no written redistribution clause for the dataset was found. That is the reason this page exists: whoever reviews the public repository can see what was checked, by whom, and when.
