# Update policy

How the data platform keeps tables fresh and correct as data arrives: freshness targets, late arrivals, reprocessing and backfills, schema evolution, and retention. Thresholds live in [`data_platform/config/sources.yml`](../../data_platform/config/sources.yml); changing them means editing that file and running `make data-codegen` (the dbt sources carry the same numbers).

## Freshness

Freshness is measured on `_loaded_at`, the instant a row was written to bronze. `dbt source freshness` (run by `bank-data test`) and the quality report both check it.

| Table | Production target (a live bank feed) | Prototype warn after | Prototype error after |
|---|---|---|---|
| transactions | Hourly micro-batches; alert after 2 hours | 48 hours | 7 days |
| daily_exchange_rates | Daily by 07:00 UTC; alert after 26 hours | 48 hours | 7 days |
| call_center_interactions, call_transcripts, satisfaction_surveys | Daily by 08:00 UTC; alert after 26 hours | 7 days | 30 days |
| complaints | Daily; alert after 26 hours (SLA clocks depend on it) | 7 days | 30 days |
| digital_events, campaign_sends | Daily; alert after 48 hours (analytics only) | 7 days | 30 days |
| customers, products | Monthly snapshot by the third business day; balances intraday in production | 7 days | 30 days |
| branches, service_agents, marketing_campaigns | Weekly or on change | 7 days | 30 days |

The prototype thresholds are loose on purpose: the organizer data is one static delivery, so the only meaningful question is whether the last ingestion ran recently. Every balance answer states its as-of instant (the snapshot business day), so staleness is visible to customers rather than hidden.

## Late arrivals

A partition can arrive days after its `process_date`, and an object can be re-delivered with corrections.

- **Ingestion** diffs the listing against the manifest by key and etag, so a late or re-delivered object is loaded whatever its date. A re-delivery replaces the object's bronze file (one file per object).
- **Incremental silver models** reprocess every `process_date` that received rows since the model's last `_loaded_at`, plus a lookback window before the latest partition (`build.lookback_days`, 7 by default), and take every bronze version of the affected keys before deduplicating. `delete+insert` on the primary key then replaces them. A late partition of any age is therefore picked up, and the result equals a full rebuild; the integration test compares table hashes of both paths on the fixture.
- **Primary-key duplicates** keep the latest `process_date` (facts) or `last_updated` (snapshots); ties break on the greatest `_etag`, then `_source_key`, then the later row in the object.
- **Removed rows.** When a re-delivered object lacks primary keys its previous version had, ingestion records a full-refresh request for the table and the next `bank-data build` runs with `--full-refresh`.

## Reprocessing and backfills

| Situation | Command |
|---|---|
| New or late objects | `make pipeline DATA_SOURCE=s3` (ingest then incremental build) |
| A model's logic changed | `uv run bank-data build --source s3 --full-refresh` |
| A contract changed (new accepted value, new range) | Edit the table spec, `make data-codegen`, then delete the affected objects' manifest rows or the warehouse and re-ingest; bronze holds only accepted rows, so quarantined rows are re-validated only when their object is reloaded |
| Start over | Remove `data/warehouse/` (the raw copies can be kept) and run `make pipeline DATA_SOURCE=s3`; unchanged raw files are reused when their MD5 matches the etag |
| Fast iteration on a subset | `make pipeline-sample DATA_SOURCE=s3` (2,000 customers by seeded hash, separate warehouse file) |

## Schema evolution

| Change | Detection | Effect |
|---|---|---|
| Additive column | Header has a column the contract lacks | Accepted into bronze as a nullable string; warning logged; `schema_events` and `backlog_items` rows in the manifest; silver ignores it until the contract adopts it (the quality report lists it for `docs/BACKLOG.md`) |
| Removed column | A contract column is missing from the header | The whole object is quarantined (`schema_removed_column`); ingestion exits 3 |
| Type change | At least half of a column's non-empty values fail to parse (`ingest.type_change_threshold`) | The whole object is quarantined (`schema_type_change`); ingestion exits 3 |
| Bad rows | Fewer failures than the threshold, or nullability, accepted values, ranges, lengths | Row-level quarantine with a reason code and the column |

Row reason codes: `type_mismatch`, `null_in_required_column`, `value_not_accepted`, `out_of_range`, `too_long`, `partition_mismatch`, `contract_violation`. Ingestion keeps exiting 3 while a quarantined batch is outstanding, so nothing downstream builds over a missing partition unnoticed; the fix is a corrected re-delivery (new etag) or a contract change. Every run records the contract version it used.

## Retention

| Data | Prototype | Production proposal |
|---|---|---|
| Raw copies (`data/warehouse/raw/`) | Kept, gitignored, to reprocess without downloading | 30 days after load; the source bucket is the system of record |
| Bronze and quarantine Parquet | Kept for the life of the warehouse | 13 months, then archived; quarantine reviewed weekly and purged 90 days after resolution |
| Silver and gold | Rebuildable from bronze at any time | Serving tables rebuilt on every run; marts kept 25 months |
| Manifest | Kept (small) | Kept for audit, with the run history |
| Committed sample | In git, bounded (rule 5) | Re-verified against the data-use terms in phase 17 |

Nothing under `data/` is ever committed. Deleting a warehouse directory is always safe: the pipeline rebuilds it from the source.
