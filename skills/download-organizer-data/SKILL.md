---
name: download-organizer-data
description: Download the hackathon organizer's S3 dataset into this repository when a contributor supplies fresh read-only credentials for that run.
---

# Download organizer data

Use this skill only for a requested download of the organizer dataset. Ask the contributor to provide the bucket, region, access key ID, and secret access key **for each run**. Do not reuse credentials from a prior run or an existing `.env` file. Do not put credentials in the skill, tracked files, command output, logs, or the final response.

From the repository root, use the existing `bank-data` S3 downloader (`make data-download` or `bank-data ingest --source s3 --download-only`). Supply the fresh credentials through a temporary, owner-readable `.env` or process environment; remove a temporary file after the command exits. Preserve any pre-existing `.env` and user data. The downloader keeps the full delivery under gitignored `data/warehouse/raw/` and supports incremental reruns.

Check the downloader's exit status and manifest summary before calling the download complete. Report counts and any failed or quarantined objects without showing keys or bucket details. Downloading alone does not build gold or seed PostgreSQL; run the pipeline and seed only when the contributor requests those steps.

Relevant repository guidance: `data_platform/README.md`, `.env.example`, and `CLAUDE.md` rules 4 and 5.
