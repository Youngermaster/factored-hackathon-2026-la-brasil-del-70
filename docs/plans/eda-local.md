# Local EDA implementation plan

Approved scope: reproduce the 13-table local EDA, conservative curated views and a progressive
Streamlit viewer. Compare workflows without assuming disputes will win. Preserve all original
CSV files. S3 ingestion, dbt deployment, model training and assistant-tool configuration are out
of scope.

Implementation order: freeze a manifest; parse and profile; trace duplicate/conflict dispositions;
validate joins; measure demand and text diversity; compare workflow evidence; publish an aggregate
report. Each phase has independently visible completion state and reproducible local outputs.

Changes belong to the existing `bank-data` package with optional DuckDB/Streamlit extras,
CLI commands and Make targets. CI installs the analysis extras to exercise synthetic fixtures.

Validation: conservation identities, stable source hashes, deterministic reruns, interrupted-run
recovery, no raw text in public artifacts, multilanguage UI smoke tests, repository quality gates.
See [the EDA guide](../analysis/EDA.md) for the concrete interfaces and curation policies.
