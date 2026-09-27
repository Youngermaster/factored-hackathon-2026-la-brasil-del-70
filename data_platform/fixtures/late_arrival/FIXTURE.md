# Fixture: late arrival and update correctness

**This is synthetic test data made by the team.** It is not organizer data and holds no real person, account, or
card. Identifiers carry `FIX`, contact details use `example.com`, and every value was invented. The files are
written by `scripts/write_late_arrival_fixture.py` (run with `--check` to compare), so edit the script, not the
CSVs.

The layout mirrors the organizer bucket prefix, so `LocalSource` reads each part unchanged.

| Part | Content | Purpose |
|---|---|---|
| `base/` | All 13 tables. Transactions for 2024-01-01 and 2024-01-03 (2024-01-02 is missing) | The first build |
| `base/` | `TRX-FIX-0001` twice in the 2024-01-01 file | Exact duplicate, removed in silver |
| `base/` | `TRX-FIX-0003` pending on 2024-01-01 and approved on 2024-01-03 | Primary-key duplicate across partitions; the later `process_date` wins |
| `base/` | `CLI-FIX-0002` twice with different `last_updated` | Snapshot primary-key duplicate; the later `last_updated` wins |
| `base/` | `TRS-FIX-0002` without the required `duration_seconds` | Row-level quarantine (`null_in_required_column`) |
| `base/` | Complaints 2024-01-03 with the extra column `channel_detail` | Additive column: accepted into bronze, warning and backlog item |
| `base/` | `CLI-FIX-0003` registered at `BR-FIX-999` | Orphan foreign key, flagged in silver |
| `late/` | The 2024-01-02 transactions partition, including `TRX-FIX-0010` declined | Arrives after the first build; its `TRX-FIX-0010` loses to the later 2024-01-03 row |
| `breaking/` | A 2024-01-04 transactions file whose `amount` values read `10,50 EUR` | Breaking type change: the batch is quarantined and ingestion exits 3 |

Tests: `data_platform/tests/integration/test_update_correctness.py` (a first build, the late partition, and an
incremental build equal a full rebuild by table hashes; the breaking file is quarantined; the additive column is
accepted).
