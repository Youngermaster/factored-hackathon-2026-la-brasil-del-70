# 0034: Bounded local gold seed into PostgreSQL for the MVP

- Status: accepted
- Date: 2026-09-27

## Context

The complete organizer delivery is present as local CSVs under `data/`. The data platform already validates
and transforms it with Pandera, dbt, and DuckDB (ADR 0007); Alembic has already defined the PostgreSQL
application schema and its row-level security. The four workflow engines need customer-owned banking data
and persistent operational state. The committed sample (ADR 0022) does not cover every published persona.
The local source directory also contains EDA outputs, documentation, and generated warehouses, none of which
is a source table.

## Considered options

1. **Copy all 13 raw tables into PostgreSQL.** One query engine, but duplicates the analytical delivery,
   bypasses validated serving contracts, and adds tables the workflows do not need.
2. **Serve every request from DuckDB gold.** Avoids a second copy of reference data, but would split customer
   reads from transactional sessions, cases, and audit records and complicate tenant isolation.
3. **Build gold from the full local CSVs and seed a bounded customer slice into PostgreSQL.** Reuses the
   existing pipeline and operational schema; the cost is a deliberate refresh/reconciliation step.

## Decision

Choose option 3 for the MVP. Local ingestion discovers only contracted table layouts before hashing, then
builds the five serving Parquet tables in its isolated `data/warehouse-local/`. The existing deterministic
seed selects 200 customers, including all 16 customer personas, with their products, transactions,
historical complaints, credit profiles, identity lookups, two staff personas, and the two synthetic demo
records. Alembic brings PostgreSQL to its existing head; no raw organizer tables or new schema revision are
needed. A read-only reconciliation command compares the selected gold rows and identity digests with the
PostgreSQL application tables. The four workflows remain in scope; this data decision does not change the
HTTP or UI delivery schedule in ADR 0025.

## Consequences

- PostgreSQL owns sessions, conversations, cases, audit, and customer-scoped service reads. DuckDB remains
  the preparation and analytical engine; the snapshot date must accompany responses.
- The seed is idempotent for row identity, but rerunning it refreshes product status from gold. Rerun before,
  not during, a demonstration that mutates card state.
- The local CSVs and generated warehouse stay gitignored. The manifest keeps source origins separate, and
  no document number or raw phone is written to the identity directory.
- Migrating all 150,000 customers later needs batch loading, checkpoints, capacity testing, and a policy for
  inactive or phone-less customers; increasing `SEED_CUSTOMERS` alone is not the migration strategy.
