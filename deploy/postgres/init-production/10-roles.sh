#!/bin/sh
# Role bootstrap for the production PostgreSQL (deploy/compose.prod.yml).
#
# The official postgres image runs this once, on an empty data directory, as POSTGRES_USER (the bootstrap
# superuser, `postgres`). That superuser is used for nothing else but backups and restores from inside the
# container; no service connects with it.
# - Owner role: POSTGRES_OWNER_USER (bank_owner). LOGIN, NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOBYPASSRLS. It owns
#   the database and the `app` schema and runs migrations, the seed, and the retention purge. Forced row-level
#   security applies to it, so it reads and writes customer tables only through its `seed` and `retention` policies.
# - Application role: POSTGRES_APP_USER (bank_app). LOGIN, NOSUPERUSER, NOBYPASSRLS, owns nothing, and only receives
#   data privileges on tables the owner creates in `app`.
# - Evaluator role: bank_evaluator, NOLOGIN, created here so the owner never needs CREATEROLE (migration 0007 only
#   creates it when it is missing).
#
# Values are read with psql's \getenv, so no password appears in a process argument list, and nothing is echoed.
# Each password comes from <NAME>_FILE when it is set (a mounted secret file: deploy/compose.prod.yml mounts them from
# the staged Key Vault values, ADR 0037), else from <NAME> itself (the integration tests).
set -eu

if [ -n "${POSTGRES_OWNER_PASSWORD_FILE:-}" ]; then
  POSTGRES_OWNER_PASSWORD="$(cat "$POSTGRES_OWNER_PASSWORD_FILE")"
  export POSTGRES_OWNER_PASSWORD
fi
if [ -n "${POSTGRES_APP_PASSWORD_FILE:-}" ]; then
  POSTGRES_APP_PASSWORD="$(cat "$POSTGRES_APP_PASSWORD_FILE")"
  export POSTGRES_APP_PASSWORD
fi

: "${POSTGRES_USER:?POSTGRES_USER must be set}"
: "${POSTGRES_DB:?POSTGRES_DB must be set}"
: "${POSTGRES_OWNER_USER:?POSTGRES_OWNER_USER must be set}"
: "${POSTGRES_OWNER_PASSWORD:?POSTGRES_OWNER_PASSWORD must be set}"
: "${POSTGRES_APP_USER:?POSTGRES_APP_USER must be set}"
: "${POSTGRES_APP_PASSWORD:?POSTGRES_APP_PASSWORD must be set}"

psql --no-psqlrc -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
\getenv db POSTGRES_DB
\getenv owner POSTGRES_OWNER_USER
\getenv owner_password POSTGRES_OWNER_PASSWORD
\getenv app_user POSTGRES_APP_USER
\getenv app_password POSTGRES_APP_PASSWORD

CREATE ROLE :"owner" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
    PASSWORD :'owner_password';
CREATE ROLE :"app_user" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
    PASSWORD :'app_password';
CREATE ROLE bank_evaluator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

ALTER DATABASE :"db" OWNER TO :"owner";
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO :"app_user";

REVOKE CREATE ON SCHEMA public FROM PUBLIC;

CREATE SCHEMA app AUTHORIZATION :"owner";
GRANT USAGE ON SCHEMA app TO :"app_user";

ALTER DEFAULT PRIVILEGES FOR ROLE :"owner" IN SCHEMA app
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner" IN SCHEMA app
    GRANT USAGE, SELECT ON SEQUENCES TO :"app_user";

ALTER ROLE :"app_user" IN DATABASE :"db" SET search_path = app;
ALTER ROLE :"owner" IN DATABASE :"db" SET search_path = app, public;
SQL
