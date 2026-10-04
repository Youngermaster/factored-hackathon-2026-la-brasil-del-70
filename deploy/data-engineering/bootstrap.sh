#!/usr/bin/env bash
# Called by VM Run Command. No remote input contains a credential.
set +x
set -euo pipefail
umask 077

install -d -m 700 /opt/la70-data /opt/la70-data/releases /opt/la70-data/runs
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl git make python3 docker.io docker-compose-v2
systemctl enable --now docker
if [[ ! -x /usr/local/bin/uv ]]; then
    curl --fail --silent --show-error --location https://astral.sh/uv/0.11.17/install.sh |
        env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh
fi

python3 - <<'PY'
import secrets
from pathlib import Path

root = Path('/opt/la70-data')
# All files are generated only on the VM and never copied into execution artifacts.
if not (root / 'owner.env').exists():
    owner, app, superuser, session, csrf = [secrets.token_hex(48) for _ in range(5)]
    common = {
        'APP_ENV': 'production', 'POSTGRES_HOST': '127.0.0.1', 'POSTGRES_DB': 'bank_agent',
        'POSTGRES_ADMIN_USER': 'bank_owner', 'POSTGRES_APP_USER': 'bank_app',
        'SESSION_SECRET': session, 'CSRF_SECRET': csrf, 'DEMO_MODE': 'true',
        'CORS_ALLOWED_ORIGINS': 'https://la70.internal',
        'ALLOW_PUBLIC_DEMO_MODE': 'true', 'RATE_LIMIT_BACKEND': 'postgres',
        'LLM_PROVIDER': 'fake', 'LLM_BUDGET_LEDGER': 'postgres',
        'BANK_DATA_DUCKDB_MEMORY_LIMIT': '3GB', 'BANK_DATA_DUCKDB_THREADS': '2',
        'BANK_DATA_INGEST_WORKERS': '2', 'BANK_DATA_DIR': '/opt/la70-data/data',
    }
    files = {
        'owner.env': {**common, 'POSTGRES_ADMIN_PASSWORD': owner},
        'api.env': {**common, 'POSTGRES_APP_PASSWORD': app},
        'postgres.env': {
            'POSTGRES_DB': 'bank_agent', 'POSTGRES_USER': 'postgres', 'POSTGRES_PASSWORD': superuser,
            'POSTGRES_OWNER_USER': 'bank_owner', 'POSTGRES_OWNER_PASSWORD': owner,
            'POSTGRES_APP_USER': 'bank_app', 'POSTGRES_APP_PASSWORD': app,
            'POSTGRES_INITDB_ARGS': '--auth-host=scram-sha-256 --auth-local=peer',
        },
    }
    for name, values in files.items():
        path = root / name
        with path.open('x') as handle:
            handle.write(''.join(f'{key}={value}\n' for key, value in values.items()))
        path.chmod(0o600)
PY
printf 'Bootstrap completed; credentials remain on the VM.\n'
