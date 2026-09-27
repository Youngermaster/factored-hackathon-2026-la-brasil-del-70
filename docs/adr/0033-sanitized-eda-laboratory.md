# 0033: Sanitized EDA laboratory in the local viewer

- Status: accepted
- Date: 2026-09-27

## Context

The phase viewer explains the pipeline, but aggregate tables alone make it difficult to inspect a
schema, understand broken relationships, or compare feasible hackathon use cases. Direct access to
the warehouse would expose personal fields, free text and arbitrary SQL, while a second web
application would duplicate run selection, language support and deployment work.

## Considered options

1. Keep the aggregate-only phase viewer and use DuckDB separately for exploration: simple, but it
   splits evidence across tools and makes a safe demo difficult.
2. Build a separate data-wrangling application with arbitrary queries: flexible, but it creates a
   much larger access-control and privacy surface.
3. Extend the existing Streamlit viewer with contract-controlled samples, a relationship map and
   an evidence-based decision laboratory.

## Decision

Use the third option. Keep the five phase pages and add a separate Laboratory navigation section.
The laboratory reads completed JSON artifacts and, only for tabular samples, opens the local
DuckDB warehouse in read-only mode. Table, layer, column and sample-size choices come from fixed
allowlists. Samples are deterministic and capped at 100 rows. A field allowlist permits entity ID
references, reviewed low-cardinality categories, month-bucketed dates and a few technical flags.
Free text, personal characteristics, fine-grained locations, financial values and outcome labels
are omitted. New contract fields stay out until reviewed; identifiers are replaced with stable
12-character hashes.
Only the sanitized sample can be downloaded.

Show relationship coverage as a graph and preserve the underlying counts for every edge. Use
traffic lights for each independent workflow dimension, without calculating a total score. Never
read `private_review.jsonl` in the viewer.

## Consequences

- The team can explore quality and feasibility in one local interface without rerunning ingestion.
- Hash references support comparison inside a sample but are not anonymization for external
  publication. The viewer remains local-only.
- Arbitrary SQL and raw-record downloads are unavailable by design.
- Changes to the laboratory do not change analytical run identity or invalidate completed phases.
- A missing warehouse disables samples while aggregate views, the relationship map and decision
  evidence remain usable.
- The decision matrix reports feasibility evidence without overriding the workflow named in the
  repository steering.
