# Phase 03 plan: data platform

Status: no plan mode for this phase (orchestrator instruction, 2026-09-26; the human pre-approved plans and delegated open questions). Written against commit `ebd2963`, after phase 08. `.env` now holds the organizer S3 values; the code reads them only through a pydantic-settings class and never prints them.

## Read-only findings from profiling the real data

Profiled from a full scratch mirror of `s3://$DATA_BUCKET/data/` (7,671 objects, 5.1 GB), never committed.

| Finding | Consequence |
|---|---|
| Six root CSVs (`branches`, `customers`, `daily_exchange_rates`, `marketing_campaigns`, `products`, `service_agents`) and seven fact prefixes laid out as `<table>/year=YYYY/month=MM/day=DD/<table>_YYYYMMDD.csv`. Every object is CSV with a UTF-8 byte order mark; there is no Parquet | The key-layout parser knows two layouts (root snapshot, daily partition); unknown keys are recorded in the manifest as `skipped` with `unknown_layout` |
| `customers` and `products` are one snapshot each, with no snapshot column; every object was written on 2026-08-31 | Only one monthly snapshot exists. Phase 10 cannot build a forward-looking label from two snapshots; recorded in `source-layout.md`, the data card, and `BACKLOG.md` for phase 10. The snapshot date is the documented end of the dataset, 2026-06-17 (configurable in `data_platform/config/sources.yml`) |
| Rows per table differ from the dictionary: transactions 4,425,008 (dictionary 5 M), digital_events 15,620,994 (10 M), call_center_interactions 686,296, call_transcripts 171,321, satisfaction_surveys 212,759, complaints 67,095, campaign_sends 1,746,801 (1,083 daily files, not 1,097), daily_exchange_rates 13,164 (12 currency pairs per day, not 3,000 rows) | The quality report states observed counts next to the dictionary counts |
| No exact duplicate rows and no primary-key duplicates in any table; no header variation across files; `process_date` always equals the partition path; no late partitions (one delivery) | The "intentional" duplicates, late arrivals, and schema evolution do not occur in the delivered snapshot. Update correctness is demonstrated with the labeled fixture, as the brief allows; the deduplication and evolution logic still runs on the real data and reports zero |
| Event timestamps fall at most one calendar day after `process_date`, and exactly the rows with a time from 00:00 to 06:00 roll over, in all three countries alike | Timestamps are interpreted as UTC and `process_date` as the business date in UTC-6 (midnight in Mexico City is 06:00 UTC). Silver keeps timestamps as UTC and adds a local time for transactions in the customer's country zone. The custom test allows `transaction_date` up to `process_date + 1 day` |
| Categorical values are Spanish or differ from the dictionary: product types (`Cuenta Ahorro`, `Tarjeta Crédito`, `Préstamo Hipotecario`, `Seguro`, ...), `Pasaporte`, `México`/`Mexico`, sentiment (`Negativo`, `Muy Positivo`), contact reasons (`Transaccional`, `Producto`, `Queja`, `Técnico`, `Comercial`, `Retención`), branch zone `Urbana`, interaction channel `Web` | Contracts accept the observed source values (the dictionary lists are incomplete or translated); silver maps them to canonical English codes through a dbt seed, and `accepted_values` tests run on the canonical codes |
| Integers arrive as `701.0`; booleans as `True`/`False` | The contract parser accepts integral decimals for integers; a non-integral value is a `type_mismatch` |
| `current_balance` is never negative on any product (minimum 0.00); on credit cards the mean balance-to-limit ratio is 0.12 and 1.3% exceed the limit; mortgages exceed their `credit_limit` in 49% of rows | Credit balance convention: `balance_is_amount_owed`. Available credit is meaningful only for revolving credit, so the domain computes it for credit cards only (loans keep balance and limit, no available credit) |
| Every `amount` is positive (minimum 5.00; transfers from 100.01, adjustments from 10.00) | Signs do not encode direction: transfers and adjustments stay `unclassified` in statement totals (recorded, no reclassification) |
| `merchant_name` appears only on purchases and holds 24 business names | No personal names in transfers; no masking needed (resolves the backlog row) |
| `amount_usd` is null on every USD transaction (2,437,979 rows) and on 5% of COP and ARS rows; rates exist for MXN, COP, ARS, USD in every direction, with no identity pair | Silver recomputes `amount_usd` with an as-of join (latest rate on or before the transaction date); USD rows use rate 1; a flag records every recomputed row |
| Products and transactions use USD, COP, ARS only; Mexican customers hold USD products | Documented as a data property; `income_currency` is still the country currency (dictionary: local currency) |
| Orphans: `customers.registration_branch_id` 149,995 of 150,000 (99.997%), `service_agents.assigned_branch_id` 831 of 833; every other foreign key resolves | Orphans are flagged, never dropped; relationship tests on these two columns are warnings with the counts in the report |
| Unique-constraint violations: 6 duplicate `product_number`, 13 duplicate `employee_code`; future `last_updated` on 9,316 customers and 25,113 products (up to 2027-06-15) | Reported as known issues; not quarantined (the rows are otherwise valid), flagged in silver |
| Survey scores: CSAT 1 to 4, NPS 2 to 7, CES 1 to 4; `nps_category` has no `Promoter` | Contract ranges by survey type (CSAT 1-5, NPS 0-10, CES 1-7) pass; distributions go to the report |
| `complaints.origin_interaction_id` is 100% null; free text (transcripts, complaint descriptions, survey comments, resolutions) is templated with placeholders such as `{monto}` and has no names or identifiers; transcripts open with one of two balance-inquiry sentences regardless of topic, and `detected_intents` is always `consulta_general` | Phase 04 and phase 10 must not treat transcripts or `detected_intents` as intent labels; recorded in the data card and the quality report |

## Decisions on the open questions

1. **Credit balance sign convention (backlog, phase 02b):** `balance_is_amount_owed` (non-negative balances everywhere; card utilization profile). The adapter exposes it as `DATASET_CREDIT_BALANCE_CONVENTION`; the domain computes available credit only for credit cards.
2. **Transfer and adjustment signs (backlog):** unsigned amounts, so they stay `unclassified`; the `direction_of` docstring states the evidence.
3. **Bronze keeps raw strings.** Bronze stores each accepted row exactly as delivered (every column a string, empty strings kept), plus the lineage columns. Typing, trimming, and empty-to-null happen in silver, as the prompt orders. The Pandera contract validates a typed copy at ingestion; each input row lands in exactly one of bronze or quarantine, and the manifest records both counts.
4. **Type change versus a bad row.** A contract column is a breaking type change when at least half of its non-empty values in a file fail to parse (threshold configurable); the whole file is quarantined and the run exits 3. Fewer failures are row-level `type_mismatch` quarantines.
5. **Backlog item for an additive column** is written to the `backlog_items` table in the manifest database and listed in the quality report, not appended to `docs/BACKLOG.md`: a pipeline run in CI must not edit tracked files.
6. **Incremental correctness with arbitrarily late partitions.** Silver fact models use `delete+insert` keyed on the primary key. A run rebuilds every `process_date` that received bronze rows since the model's last `_loaded_at`, plus a lookback window (7 days by default), and for those rows takes every bronze version of the same keys before deduplicating. A late partition older than the lookback is therefore still picked up, and incremental equals full.
7. **Sampling** happens in silver (dbt vars `sample_customers`, `sample_seed`), ranked by `sha256(seed || ':' || customer_id)`, so bronze and the manifest always describe the full delivery. `make pipeline-sample` writes to its own warehouse file and gold directory.
8. **Committed sample** is extracted from bronze of the full warehouse, keeps the S3 layout, and limits fact rows to the last 365 days of the dataset to bound the file count. Customers are taken in seeded hash order; after a minimum count, a customer is added only when it covers a missing case (cards, balances, payments and transfers in every status, credit products with and without days past due, income present and missing, a declined card purchase, a complaint). `product_number` and `ip_address` are pseudonymized as well, although rule 5 does not list them.
9. **Snapshot date and `balance_as_of`:** snapshot date 2026-06-17; `balance_as_of` is the end of that business day, 2026-06-18T05:59:59Z.
10. **Credit profile derivation:** credit products are credit cards, personal loans, and mortgages that are not closed; `credit_product_count` counts them; `max_days_past_due` is their maximum (null when none is known); `total_credit_limit` sums their limits when they share one currency; `utilization` is the credit-card balance over the credit-card limit (revolving utilization) when one currency; tenure is full months from `registration_date` to the snapshot date; income currency is the country currency.
11. **Local source warehouse.** `bank-data ingest --source auto` uses S3 when `DATA_BUCKET` is set and otherwise the committed sample; the default warehouse directory is `data/warehouse` for S3 and `data/warehouse-local` for a local source, so the two never mix in one manifest (the manifest also refuses a second source).
12. **dbt runs in a subprocess** with an explicit environment that carries no AWS variables, anonymous usage stats and version checks off.

## Files to create or change

| Path | Change |
|---|---|
| `data_platform/pyproject.toml`, `services/api/pyproject.toml`, `uv.lock` | duckdb, dbt-core, dbt-duckdb, pandera[pandas], boto3, pydantic, pydantic-settings (bank-data); duckdb (bank-agent) |
| `data_platform/src/bank_data/settings.py`, `paths.py`, `errors.py`, `logs.py` | Settings (S3 values as `SecretStr`, DuckDB limits, lookback), warehouse paths, typed errors with codes and exit codes, logging |
| `data_platform/src/bank_data/contracts/` | `tables.py` (13 table specs from the dictionary plus profiling), `parsing.py`, `schemas.py` (Pandera, strict), `validation.py` (quarantine reasons), `evolution.py` (schema diff) |
| `data_platform/src/bank_data/ingest/` | `source.py` (port), `s3.py`, `local.py`, `layout.py`, `manifest.py`, `bronze.py`, `runner.py` |
| `data_platform/src/bank_data/transform/` | `dbt.py` (subprocess runner), `codegen.py` (sources and silver contract YAML from the table specs, with a `--check` mode) |
| `data_platform/src/bank_data/reports/` | `quality.py` (quality report), `lineage.py` (Mermaid from `manifest.json`) |
| `data_platform/src/bank_data/sample/` | `extract.py`, `pseudonyms.py`, `readme.py` |
| `data_platform/src/bank_data/cli.py` | `ingest`, `build`, `test`, `report`, `lineage`, `sample`, `codegen` |
| `data_platform/config/sources.yml` | Layout, snapshot date, freshness thresholds, lookback |
| `data_platform/dbt/` | Project, profile, macros (bronze source, sampling, dedup, incremental window), seeds (canonical value map), silver models for 13 tables, `quarantine_orphans`, gold serving, ML inputs, and five marts, generic tests |
| `data_platform/fixtures/late_arrival/` | `FIXTURE.md`, `base/`, `late/`, `breaking/` |
| `data_platform/sample/` | Generated CSVs and README |
| `services/api/src/bank_agent/adapters/persistence/duckdb/` | Gold schema constants, readers for customers, products, transactions, complaints, credit profiles; `DATASET_CREDIT_BALANCE_CONVENTION` |
| `services/api/src/bank_agent/domain/accounts.py`, `product.py` | Available credit for revolving credit only; docstrings with the recorded conventions |
| `scripts/checks/check_data_sample.py` | The rule 5 guard |
| `Makefile`, `.github/workflows/ci.yml` | `data-download`, `pipeline`, `pipeline-sample`, `data-sample`, `data-report`, `lineage`; the guard in `check` and in CI |
| Docs | `data_platform/README.md`, `docs/data/{data-card,update-policy,source-layout,lineage,quality-report}.md`, `docs/workflows/data-pipeline.md`, ADRs 0007 and 0022, `workflow-registry.md`, `ports-and-adapters.md`, `docs/README.md`, BACKLOG, PROGRESS |

## Tests

- Unit (`data_platform/tests/unit`): schema diff classification; parsing and Pandera validation with reason codes; deduplication on small frames (through DuckDB SQL macros compiled for the test); manifest diffing; key-layout parsing; the as-of exchange-rate join; sampling determinism; credentials absent from exception messages and logs (fake values injected); `S3Source` with the botocore `Stubber`; `LocalSource`; codegen output is current; pseudonyms are deterministic and format-valid; the lineage renderer; the quality report renderer on a tiny warehouse.
- Integration (`data_platform/tests/integration`): `LocalSource` end to end on the fixture; `dbt build` on the fixture (models and tests pass); first build, late partition, incremental build equals a full rebuild by table hashes; the breaking file is quarantined and the run exits 3; the additive column is accepted; the bank-agent DuckDB readers read the fixture's gold output; the sample extractor is deterministic, capped, closed, pseudonymized, and covers every workflow.
- Contract suites (`services/api/tests/contracts`): a `DuckDbBackend` (readers only, integration marker) that writes the contract dataset as gold Parquet.
- Guard (`scripts/tests/unit/test_check_data_sample.py`): passing and failing inputs.

## Risks

- Full ingestion validates 7,671 files with Pandera; measured runtime goes into the docs. DuckDB memory and threads are configurable.
- dbt adds startup time to integration tests; builds share a module-scoped fixture.
- dbt-core, pandas, and botocore are large (the venv grows by about 340 MB); DuckDB, dbt-duckdb, and Pandera are named in the CLAUDE.md stack and boto3 in the prompt. Sizes are recorded for human review.
- The UTC interpretation of timestamps is an inference from data; it is documented as such.

## Open questions

None blocking. The data-use terms are not available in the repository (the dictionary transcription has none); the data card records that they must be checked before the repository is made public (phase 17), and the sample is committed under rule 5 in the meantime.
