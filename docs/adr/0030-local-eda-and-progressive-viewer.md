# 0030: Local EDA with a progressive aggregate viewer

- Status: accepted
- Date: 2026-09-27

## Context

The team needs to compare banking workflows using the organizer's imperfect CSV dataset
before implementing a full ingestion platform. The local copy contains 13 tables and about
5.35 GB. Duplicate events, repeated text templates and conflicting entity keys must be
separated. A local machine has about 8 GB RAM, and the team wants to inspect each completed
analysis phase in Streamlit.

## Considered options

1. Notebook-centric analysis loading dataframes into memory: convenient for exploration,
   but difficult to constrain memory and reproduce cell execution order.
2. A full S3/dbt/PostgreSQL pipeline first: appropriate for later operations, but delays
   the evidence needed to select a workflow.
3. CLI-driven DuckDB analysis with immutable local artifacts and a separate Streamlit viewer:
   supports bounded local processing, independent phase execution and a lightweight interface.

## Decision

Use the third option inside the existing bank-data package. Preserve original files, identify
runs by content and code fingerprints, checkpoint committed ingestion batches, and publish
phase status separately from aggregate artifacts. The viewer reads completed aggregates;
filtering and rendering never trigger CSV ingestion or expose original records.

Collapse only exact parsed rows. Quarantine conflicting primary keys and required-field
failures; retain semantic anomalies and orphan rows with audit evidence. Do not assume that
matching transcript text means duplicate events. Use repetition groups for evaluation planning.

## Consequences

- Analysis and the viewer are independently reproducible and can be resumed locally.
- A malformed batch rolls back atomically and is retried per file. Resource failures stop
  the phase instead of being reported as data corruption.
- DuckDB and Streamlit are optional extras; their transitive dependencies enlarge the local
  development environment. Streamlit constrains websockets below 17 in the shared lockfile.
- The viewer is local-only. Shared hosting would require an explicit access-control design.
- Broad contact categories, repeated templates and missing links may prevent a defensible
  workflow winner. The report must expose uncertainty rather than fabricate precise demand.
- Human review of the local stratified sample remains necessary before treating labels as
  evaluation ground truth. The full S3/dbt and production seeding phases remain separate.
