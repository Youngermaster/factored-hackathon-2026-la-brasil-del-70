# 0007: dbt-duckdb and Pandera for the data platform

- Status: accepted
- Date: 2026-09-26

## Context

The brief assesses data engineering on extraction and transformation, contracts with strict schema enforcement, quality checks, lineage, and an update or freshness policy. The organizer delivery is 7,671 CSV objects (5.3 GB, 23.5 million rows) in an S3 bucket, one static delivery, and the prototype runs on laptops and one small deployment host. The team is small, the deadline is ten days away, and every evaluator must be able to rebuild the tables, including without organizer credentials (the committed sample).

## Considered options

1. **Spark or Databricks with Delta tables.** Scales far beyond the data and brings a lakehouse, time travel, and managed jobs. But it needs a cluster or a paid workspace, slow start-up, and credentials evaluators do not have; local Spark on 23 million rows is slower than an embedded engine and heavy to install.
2. **pandas or Polars scripts with hand-written checks.** Light, but transformations, dependencies, tests, and lineage would be bespoke code, and incremental logic hard to review.
3. **Great Expectations for data quality** (with either engine). A rich expectation library and data docs, but a large dependency and configuration surface, its own context and store layout, and a second place to declare what the dbt tests already declare.
4. **DuckDB with dbt-duckdb for transformations, and Pandera for ingestion contracts.** DuckDB is an embedded, columnar engine that reads and writes Parquet natively and handles the full delivery on one machine in minutes. dbt gives declared models, enforced model contracts, generic tests, incremental materializations, sources with freshness, and a manifest for lineage. Pandera validates each object at the door with typed, strict schemas and reports failures per row and column.

## Decision

Option 4.

- **Ingestion** validates every object with a strict Pandera schema generated from the table specs (one source of truth in `bank_data.contracts.tables`) and writes accepted raw rows to bronze Parquet and rejected rows to quarantine, with a reason and a column. Schema evolution is decided before Pandera runs.
- **Transformations** are dbt models: silver `stg_` models (typed, canonical, deduplicated; facts incremental with `delete+insert` on the primary key over the partitions loaded since the last run plus a lookback window), silver views for orphan flags and derived checks, and gold serving Parquet (external materialization) plus ML inputs and marts. Model contracts are enforced; the source and silver YAML are generated from the same specs and checked for staleness in `make check`.
- **Quality** has three layers: row contracts at ingestion, dbt tests (unique, not_null, accepted_values, relationships, custom), and the generated quality report.
- **Lineage** comes from dbt's manifest, rendered as Mermaid.

## Consequences

- One machine rebuilds everything: 20 minutes for the first full ingestion, about two minutes for a full dbt build, seconds from the committed sample. CI builds the fixture with real dbt and DuckDB.
- DuckDB is single-writer: one build per warehouse file at a time. Full, subset, and fixture builds use separate files.
- dbt-core and its dependencies are large (the virtual environment grew by about 340 MB with pandas, botocore, and dbt); they stay out of the API runtime image, which needs only the `duckdb` wheel for the gold readers.
- Pandera patches `typing._GenericAlias.__call__` on import; the project restores the original (it uses only `DataFrameSchema`), with a regression test, because the bank-agent identifiers are `Annotated[NewType]` aliases.
- **When to move to a lakehouse.** Revisit when any of these holds: the data no longer fits one machine's disk or a full build exceeds the update window (roughly beyond 500 GB or hourly SLAs on hundreds of millions of rows); several writers need concurrent, transactional writes; data arrives as streams rather than files; or governance needs catalog-level access control and time travel. dbt models port to dbt-spark or dbt-databricks with the SQL dialect adjusted, and the Pandera contracts can run on Spark frames, so the move changes the engine, not the design.
