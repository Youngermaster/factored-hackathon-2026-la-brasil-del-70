#!/bin/sh
# Role bootstrap for the development and test PostgreSQL containers.
#
# The official postgres image runs this once, on an empty data directory, as POSTGRES_USER.
# - Owner role: POSTGRES_USER (bank_owner). It owns the database and the `app` schema and runs
#   migrations. In development and tests it is the image's bootstrap superuser; production uses a
#   non-superuser owner (phase 16).
# - Application role: POSTGRES_APP_USER (bank_app). LOGIN, NOSUPERUSER, NOBYPASSRLS, owns nothing,
#   and only receives data privileges on tables the owner creates in `app`, so row-level security
#   always applies to it.
#
# Values are read with psql's \getenv, so the password never appears in a process argument list,
# and nothing is echoed.
set -eu

: "${POSTGRES_USER:?POSTGRES_USER must be set}"
: "${POSTGRES_DB:?POSTGRES_DB must be set}"
: "${POSTGRES_APP_USER:?POSTGRES_APP_USER must be set}"
: "${POSTGRES_APP_PASSWORD:?POSTGRES_APP_PASSWORD must be set}"

psql --no-psqlrc -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
\getenv owner POSTGRES_USER
\getenv db POSTGRES_DB
\getenv app_user POSTGRES_APP_USER
\getenv app_password POSTGRES_APP_PASSWORD

CREATE ROLE :"app_user" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
    PASSWORD :'app_password';

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
