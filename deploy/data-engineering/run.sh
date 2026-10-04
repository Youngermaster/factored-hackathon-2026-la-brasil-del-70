#!/usr/bin/env bash
# Execute one versioned batch on the VM. The database seed runs only on an empty database.
set +x
set -euo pipefail
umask 077

revision=${1:?committed revision required}
source_kind=${2:-sample}
case "$source_kind" in sample|local|s3) ;; *) exit 2 ;; esac
[[ "$revision" =~ ^[0-9a-f]{40}$ ]] || exit 2
root=${3:-/opt/la70-data}
source_digest=${4:-}
if [[ "$source_kind" == local ]]; then
    [[ "$source_digest" =~ ^[0-9a-f]{64}$ ]] || exit 2
fi
release="$root/releases/$revision"
cd "$release"
exec 9>"$root/pipeline.lock"
flock -n 9 || { printf 'Another pipeline execution is active.\n' >&2; exit 1; }
run_id="$(date -u +%Y%m%dT%H%M%SZ)-${revision:0:12}"
run_dir="$root/runs/$run_id"
mkdir -p "$run_dir"
printf '%s\n' "$run_id" > "$root/latest-run"
printf 'running\n' > "$run_dir/status"
exec >"$run_dir/execution.log" 2>&1

warehouse="$root/data/warehouse-$source_kind"
finish() {
    result=$?
    trap - EXIT
    if [[ "$result" == 0 ]]; then status=succeeded; else status=failed; fi
    printf '%s\n' "$status" > "$run_dir/status"
    if [[ -x "$root/venv/$revision/bin/python" ]]; then
        if ! "$root/venv/$revision/bin/python" deploy/data-engineering/runtime.py evidence \
            "$run_dir" "$warehouse" "$revision" "$source_kind" "$status"; then
            status=failed
            [[ "$result" != 0 ]] || result=1
        fi
    fi
    printf '%s\n' "$status" > "$run_dir/status"
    exit "$result"
}
trap finish EXIT

export UV_PROJECT_ENVIRONMENT="$root/venv/$revision"
export UV_CACHE_DIR="$root/uv-cache"
uv sync --frozen --all-packages
set -a
# shellcheck source=/dev/null
source "$root/owner.env"
set +a
export BANK_DATA_WAREHOUSE_DIR="$root/data/warehouse-$source_kind"
args=(--source "$source_kind")
if [[ "$source_kind" == local ]]; then
    args+=(--local-dir "$root/source")
elif [[ "$source_kind" == s3 ]]; then
    # Credentials must be provisioned by the operator on the VM, never supplied to Run Command.
    [[ -f "$root/s3.env" ]] || { printf 'Provision protected S3 settings on the VM first.\n'; exit 2; }
    set -a
    # shellcheck source=/dev/null
    source "$root/s3.env"
    set +a
fi

step() {
    printf '%s started\n' "$1"
    local name=$1
    shift
    "$@" >"$run_dir/$name.log" 2>&1
    printf '%s succeeded\n' "$name"
}
if [[ "$source_kind" == local ]]; then
    step source uv run --frozen python deploy/data-engineering/source.py restore \
        "$root/sources/$source_digest.tar.gz" "$root/source" "$source_digest"
fi
step ingest uv run --frozen bank-data ingest "${args[@]}"
step build uv run --frozen bank-data build "${args[@]}"
step validation uv run --frozen bank-data test "${args[@]}"
step quality uv run --frozen bank-data report "${args[@]}" --output "$run_dir/quality.md"
step lineage uv run --frozen bank-data lineage "${args[@]}" --output "$run_dir/lineage.md"
printf '\nExecution revision: %s.\n' "$revision" >> "$run_dir/quality.md"
printf '\nExecution revision: %s.\n' "$revision" >> "$run_dir/lineage.md"
step retrieval uv run --frozen bank-agent index build --output "$root/data/retrieval-index"
export RETRIEVAL_INDEX_SOURCE=stored
export RETRIEVAL_INDEX_DIR="$root/data/retrieval-index"
compose=(docker compose -f deploy/data-engineering/compose.yml)
if [[ -f "$root/datagrip.compose.yml" ]]; then
    compose+=(-f "$root/datagrip.compose.yml")
fi
step postgres "${compose[@]}" up -d --wait
step migrations uv run --frozen bank-agent db upgrade
if uv run --frozen python deploy/data-engineering/runtime.py empty; then
    step seed uv run --frozen bank-data seed "${args[@]}" --customers 200
else
    result=$?
    [[ "$result" == 10 ]] || exit "$result"
    printf 'Existing database retained; automatic reseeding refused.\n' > "$run_dir/seed.log"
fi
step reconciliation uv run --frozen bank-data verify-seed "${args[@]}" --customers 200 --check-values
unset POSTGRES_ADMIN_PASSWORD
set -a
# shellcheck source=/dev/null
source "$root/api.env"
set +a
step application uv run --frozen python deploy/data-engineering/smoke.py "$run_dir/application.json"
mkdir -p "$run_dir/gold"
cp "$warehouse"/gold/*_serving.parquet "$run_dir/gold/"
"${compose[@]}" exec -T postgres \
    pg_dump -U postgres -d bank_agent -Fc > "$run_dir/database.dump"
printf 'All pipeline stages completed.\n'
