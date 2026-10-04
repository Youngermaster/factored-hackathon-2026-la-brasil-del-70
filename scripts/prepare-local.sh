#!/usr/bin/env bash
# Prepare the development database and sample data without deleting volumes.
set +x
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

for tool in docker make uv; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        printf 'Required command is missing: %s\n' "$tool" >&2
        exit 1
    fi
done
docker compose version >/dev/null
docker info >/dev/null

make env
printf 'Starting development PostgreSQL...\n'
docker compose -f docker-compose.yml up -d --wait postgres

printf 'Synchronizing development database passwords...\n'
# Compose supplies the credentials; do not parse .env or put secrets in arguments.
# The local socket authenticates the bootstrap owner inside the dev container.
# Suppress SQL diagnostics, which can include password literals on failure.
if ! docker compose -f docker-compose.yml exec -T postgres sh -eu -c '
    psql --no-psqlrc --quiet -v ON_ERROR_STOP=1 \
        --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"
' >/dev/null 2>&1 <<'SQL'
\getenv owner POSTGRES_USER
\getenv owner_password POSTGRES_PASSWORD
\getenv app_user POSTGRES_APP_USER
\getenv app_password POSTGRES_APP_PASSWORD
BEGIN;
SELECT format('ALTER ROLE %I PASSWORD %L', :'owner', :'owner_password') \gexec
SELECT format('ALTER ROLE %I PASSWORD %L', :'app_user', :'app_password') \gexec
COMMIT;
SQL
then
    printf 'Password synchronization failed. Check that this dev volume contains the configured owner and application roles. No volume was deleted.\n' >&2
    exit 1
fi

make db-upgrade
make pipeline DATA_SOURCE=sample
make seed DATA_SOURCE=sample

printf '\nLocal preparation completed. Start these commands in separate terminals:\n'
printf '%s\n' \
    'DEMO_MODE=true uv run --frozen uvicorn bank_agent.asgi:create_app --factory --reload' \
    'VITE_DEMO_MODE=true pnpm --dir apps/web run dev' \
    'Open http://localhost:5173'
