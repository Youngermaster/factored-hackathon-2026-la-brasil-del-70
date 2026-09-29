---
name: setup-postgres-data
description: Set up this repository's local PostgreSQL database on a developer machine, apply its migrations, and load the supported demo data from an existing data warehouse or the committed sample. Use for onboarding, rebuilding an empty local database, or copying a prepared data directory to another developer.
---

# Set up PostgreSQL and load data

Run this workflow from the repository root. Use the repository's Docker Compose service, migrations, and `bank-data seed`; do not create tables by hand or import Parquet/CSV directly with `COPY`. The seed maps gold data into the application schema, derives identity records, applies row-level-security migrations, and upserts all rows in one transaction.

## Inspect before changing anything

1. Read `docker-compose.yml`, `.env.example`, `Makefile`, and `data_platform/README.md` in case the repository has changed since this skill was written.
2. Confirm Docker with Compose and `uv` are installed. If either executable is missing, tell the developer exactly which prerequisite is missing and stop; do not install system software without a request.
3. Preserve an existing `.env`. Never print, log, commit, or replace its secret values. If `.env` is absent, create it from `.env.example`, then populate at least:
   - `POSTGRES_ADMIN_PASSWORD`
   - `POSTGRES_APP_PASSWORD`
   - `SESSION_SECRET` with at least 32 random bytes
   Use newly generated local-development secrets. Keep `.env` untracked.
4. Install the locked Python workspace when needed with `uv sync --all-packages --frozen`.

## Select the data source

Choose the first matching source and use that same source for every command:

| Evidence | Source | Gold directory |
|---|---|---|
| `data/warehouse/gold/customers_serving.parquet` exists | `s3` | `data/warehouse/gold/` |
| `data/warehouse-sample/gold/customers_serving.parquet` exists | `sample` | `data/warehouse-sample/gold/` |
| Neither exists | `sample` | build it from the committed `data_platform/sample/` |

A copied full `data/` directory should retain `data/warehouse/`, including its gold Parquet files. Once those gold files exist, seeding with `--source s3` is offline and does not require organizer AWS credentials.

Files under `data/eda/<run>/curated/` are exploratory artifacts and are not valid seed input. Do not rename or copy them into a gold directory. If they are the only copied files, use the committed sample route below, or explain that the developer must receive the original pipeline warehouse or source data before the full organizer dataset can be loaded.

For a nonstandard prepared warehouse, set `BANK_DATA_WAREHOUSE_DIR` to its directory and select the source that produced it. Do this only after checking that its `gold/` contains `customers_serving.parquet`, `products_serving.parquet`, `transactions_serving.parquet`, `complaints_serving.parquet`, and `credit_profiles_serving.parquet`.

## Create the database and load it

Start only PostgreSQL and wait for its health check:

```sh
docker compose up -d --wait postgres
docker compose ps postgres
```

On the volume's first creation, `deploy/postgres/init/10-roles.sh` creates the owner role, application role, and `app` schema. The passwords in `.env` must match the values used when that volume was first initialized. If an existing volume was created with unknown or different credentials, do not delete it automatically. Report the mismatch and ask before running `docker compose down --volumes`, because that erases the local database.

On a fresh volume, inspect `docker compose logs --no-color postgres` before seeding. Require successful `CREATE ROLE` and `CREATE SCHEMA` entries and no init-script error. A healthy server alone is insufficient because PostgreSQL can start after an init script fails. The repository's `.gitattributes` keeps shell scripts at LF on Windows; `/bin/sh^M: bad interpreter` means the working copy did not honor that rule and the new, incomplete volume must be recreated after correcting the line endings.

If no prepared gold directory was found, build and test the offline committed sample:

```sh
uv run bank-data ingest --source sample
uv run bank-data build --source sample
uv run bank-data test --source sample
```

Load the selected gold data. The command applies every pending PostgreSQL migration before performing the idempotent upsert:

```sh
uv run bank-data seed --source sample --customers 200
```

For copied full data, replace `sample` with `s3`:

```sh
uv run bank-data seed --source s3 --customers 200
```

Use a different customer count only when the developer requests it. The seed intentionally loads the requested deterministic demo subset rather than every organizer row. Rerunning the same command is safe and leaves the same seeded rows.

The bounded `sample` source automatically uses `data_platform/seed/personas.sample.yaml`; a full or copied organizer warehouse uses `data_platform/seed/personas.yaml`. The customer count is a target ceiling. The committed sample can load fewer eligible customers than requested, so report the actual count printed by the seed.

## Verify the result

Require all of the following before reporting success:

- `docker compose ps postgres` reports the service as healthy.
- On a fresh volume, the PostgreSQL init logs show that the application role and `app` schema were created without errors.
- The seed exits with status 0 and prints counts for `customers`, `staff_members`, `identity_directory`, `products`, `transactions`, `historical_complaints`, `credit_profiles`, `dispute_cases`, and `credit_applications`.
- `uv run bank-agent db upgrade` exits successfully; it is an idempotent migration check.
- No secret values or organizer data were added to Git. Check `git status --short` and use `git check-ignore .env data/warehouse/gold/customers_serving.parquet` to confirm the local configuration and warehouse data remain ignored.

If the seed says that no gold tables exist, return to source selection and build the correct source. If connection or authentication fails, compare only the variable names, host, port, database, and role names with `.env.example`; never display passwords. Do not work around migration, role, or row-level-security failures by granting superuser privileges to the application role.

Report which source was loaded, the requested customer target, the table counts printed by the seed, and whether PostgreSQL is healthy. Mention that the PostgreSQL rows are stored in the Compose `pgdata` volume and survive `docker compose down`; `docker compose down --volumes` removes them.
