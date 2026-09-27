# Source layout

The organizer bucket as discovered in phase 03 (listing and full download on 2026-09-26). The bucket name and credentials live only in `.env`; nothing here depends on them.

## Objects

7,671 objects, 5.3 GB, all CSV (UTF-8 with a byte order mark, comma separated, a header row, quoted fields that may span lines). Every object was last modified on 2026-08-31, which means a single delivery: no partition arrived late, and no object was re-delivered.

| Layout | Key pattern under `data/` | Tables | Objects |
|---|---|---|---|
| Root snapshot | `<table>.csv` | `branches`, `customers`, `daily_exchange_rates`, `marketing_campaigns`, `products`, `service_agents` | 6 |
| Daily partition | `<table>/year=YYYY/month=MM/day=DD/<table>_YYYYMMDD.csv` | `transactions`, `call_center_interactions`, `call_transcripts`, `satisfaction_surveys`, `digital_events`, `complaints`, `campaign_sends` | 1,097 each (2023-06-17 to 2026-06-17), except `campaign_sends` with 1,083 (from 2023-07-01) |

`bank_data.ingest.layout.parse_key` implements exactly these two patterns (Parquet files with the same names are accepted too). Any other key is recorded in the manifest as `skipped` with `unknown_layout` and never loaded.

## Partitions and dates

- Inside every daily file, `process_date` equals the date in the key; the contract quarantines a row whose `process_date` differs (`partition_mismatch`). None does.
- Event timestamps (`transaction_date`, `interaction_date`, `event_date`, `creation_date`, `send_date`) fall on `process_date` or on the next calendar day, and exactly the rows between 00:00 and 06:00 roll over, in all three countries alike. The timestamps are therefore read as UTC and `process_date` as the business date in UTC-6 (midnight in Mexico City is 06:00 UTC). Survey answers (`survey_date`) arrive up to two days after `process_date`.
- Root snapshot files carry no date. Their partition is the documented end of the dataset, 2026-06-17 (`dataset.snapshot_date` in `data_platform/config/sources.yml`), and product balances are served as of the end of that business day, 2026-06-18T05:59:59Z.

## Monthly snapshots of customers and products

The dictionary describes `customers` and `products` as monthly snapshots, but the delivery holds **one snapshot of each** (one root file, no snapshot column; `last_updated` is a row attribute, not a snapshot key). Phase 10 needs at least two snapshots to build a forward-looking credit risk label strictly after its features; with one, `credit_risk_inputs` carries features and days past due at the same snapshot date, and phase 10 must either find another label (recorded in `docs/BACKLOG.md`) or state the limitation.

## Row counts

| Table | Dictionary | Delivered |
|---|---|---|
| branches | 350 | 350 |
| customers | 150,000 | 150,000 |
| products | 400,000 | 400,000 |
| service_agents | 1,200 | 1,200 |
| marketing_campaigns | 200 | 200 |
| daily_exchange_rates | 3,000 | 13,164 (1,097 days times 12 currency pairs) |
| transactions | 5,000,000 | 4,425,008 |
| call_center_interactions | 800,000 | 686,296 |
| call_transcripts | 200,000 | 171,321 |
| satisfaction_surveys | 250,000 | 212,759 |
| digital_events | 10,000,000 | 15,620,994 |
| complaints | 80,000 | 67,095 |
| campaign_sends | 2,000,000 | 1,746,801 |

## Headers and schema

Every object of a table has the same header, in the dictionary's column order; no column was added or removed across files. The schema-evolution detector therefore reports no event on the real data; the fixture in `data_platform/fixtures/late_arrival/` exercises additive and breaking changes.

## How this was discovered

`aws s3 ls --recursive` over the prefix for the key list, then a full mirror profiled with DuckDB (headers per file, `process_date` against the key, timestamp offsets by hour and country, distinct values, nulls, orphans). The same checks now run on every build through the contracts, the dbt tests, and the quality report.
