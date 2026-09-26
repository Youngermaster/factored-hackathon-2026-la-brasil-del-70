# bank-data: data platform

## Responsibility

`bank-data` turns the organizer dataset into trustworthy, versioned tables for the rest of the system. It owns:

- ingestion from the organizer S3 bucket or a local directory, driven by a manifest (phase 03);
- ingestion contracts with Pandera and schema-evolution detection (phase 03);
- the dbt-duckdb project that builds bronze, silver, and gold layers (phase 03);
- data-quality and workflow-selection reports (phases 03 and 04);
- loading the demo subset into PostgreSQL (`bank-data seed`, phase 05).

Raw and derived data live under the repository `data/` directory, which is gitignored. Only small synthetic fixtures, each labeled as a fixture, are committed.

## Layout

| Path | Content |
|---|---|
| `src/bank_data/` | The Python package; `cli.py` is the `bank-data` entry point |
| `tests/unit/` | Unit tests (no network, no database) |
| `tests/integration/` | Integration tests against real DuckDB files (added with the pipeline) |

Later phases add `dbt/`, `fixtures/`, `mappings/`, `seed/`, and `analysis/` beside `src/`, because they are project assets rather than Python modules.

## Public interfaces

- The `bank-data` command. Today it exposes `version` and `--help`:

  ```bash
  uv run bank-data --help
  uv run bank-data version
  ```

- Later phases add `ingest`, `pipeline`, `report`, `analysis`, and `seed` subcommands, each wired to a Make target.

## How to extend

- **New command:** add a function decorated with `@app.command()` in `src/bank_data/cli.py`, or a sub-application registered with `app.add_typer(...)` when a command group grows. Keep the command thin: parse arguments, resolve dependencies, call a function that is tested on its own.
- **New data origin:** implement the `DataSource` port (phase 03) as a new adapter; the ingestion code does not change.
- **Settings:** credentials come only from environment variables through a pydantic-settings class. Never print or log them.

## How to test

```bash
uv run pytest data_platform/tests -m unit
make test-unit
```

Coverage for `data_platform/src` is gated at 80% line coverage by `make check`.
