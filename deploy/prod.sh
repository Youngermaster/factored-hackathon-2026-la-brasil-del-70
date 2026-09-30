#!/usr/bin/env bash
# Operate the production stack on one host (deploy/README.md). Run from the repository checkout on the server.
#
#   deploy/prod.sh init-env         create deploy/.env.production from the template with fresh secrets (mode 600)
#   deploy/prod.sh check            validate the env file (required values set, never printed) and the compose file
#   deploy/prod.sh build            build the web, api, and job images, tagged with the current git commit
#   deploy/prod.sh up               migrate, then start (OBS=1 adds the obs profile, OLLAMA=1 the ollama profile)
#   deploy/prod.sh seed             load the demo personas and customers (run once after the first up)
#   deploy/prod.sh update           git pull --ff-only, back up, build, migrate, start
#   deploy/prod.sh backup           pg_dump into deploy/backups/ (mode 600)
#   deploy/prod.sh restore <file>   restore a backup (stops the API and the purge while it runs)
#   deploy/prod.sh rollback         start the previously deployed image tag again
#   deploy/prod.sh purge            run the retention purge once now
#   deploy/prod.sh smoke            run deploy/smoke_test.sh against PUBLIC_ORIGIN
#   deploy/prod.sh status | logs [service]
#   deploy/prod.sh down             stop the stack, keep the data
#   deploy/prod.sh destroy --yes    take the demo down for good: containers, volumes (database, certificates), images
#
# Environment: ENV_FILE (default deploy/.env.production), PROJECT (default bank-agent-prod), IMAGE_TAG (default the
# tag of the last deploy, else the current commit). The script never prints a secret value.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT}/deploy/.env.production}"
PROJECT="${PROJECT:-bank-agent-prod}"
STATE_DIR="${ROOT}/deploy/.state"
BACKUP_DIR="${BACKUP_DIR:-${ROOT}/deploy/backups}"
REQUIRED=(SITE_ADDRESS PUBLIC_ORIGIN POSTGRES_SUPERUSER_PASSWORD POSTGRES_ADMIN_PASSWORD POSTGRES_APP_PASSWORD
  SESSION_SECRET CSRF_SECRET)
SECRETS=(POSTGRES_SUPERUSER_PASSWORD POSTGRES_ADMIN_PASSWORD POSTGRES_APP_PASSWORD SESSION_SECRET CSRF_SECRET
  GRAFANA_ADMIN_PASSWORD)

say() { printf '%s\n' "$*" >&2; }
fail() { say "error: $*"; exit 1; }

env_value() {
  # The value of $1 in the env file (last assignment wins), without printing it.
  sed -n "s/^$1=//p" "${ENV_FILE}" | tail -n 1
}

current_tag() {
  # IMAGE_TAG when given (rollback sets it), else the checked-out commit, which is what `build` tagged.
  if [[ -n "${IMAGE_TAG:-}" ]]; then printf '%s' "${IMAGE_TAG}"; return; fi
  git -C "${ROOT}" rev-parse --short=12 HEAD
}

profiles() {
  local flags=()
  [[ "${OBS:-0}" == "1" ]] && flags+=(--profile obs)
  [[ "${OLLAMA:-0}" == "1" ]] && flags+=(--profile ollama)
  printf '%s\n' "${flags[@]:-}"
}

compose() {
  local extra=()
  while IFS= read -r flag; do [[ -n "${flag}" ]] && extra+=("${flag}"); done < <(profiles)
  IMAGE_TAG="$(current_tag)" docker compose -f "${ROOT}/deploy/compose.prod.yml" --env-file "${ENV_FILE}" \
    -p "${PROJECT}" ${extra[@]+"${extra[@]}"} "$@"
}

cmd_init_env() {
  [[ -e "${ENV_FILE}" ]] && fail "${ENV_FILE} exists; edit it instead"
  umask 077
  local line name
  while IFS= read -r line || [[ -n "${line}" ]]; do
    name="${line%%=*}"
    if [[ "${line}" == *= && " ${SECRETS[*]} " == *" ${name} "* ]]; then
      printf '%s=%s\n' "${name}" "$(openssl rand -hex 32)"
    else
      printf '%s\n' "${line}"
    fi
  done < "${ROOT}/deploy/.env.production.example" > "${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
  say "wrote ${ENV_FILE} (mode 600) with fresh secrets; now set SITE_ADDRESS, PUBLIC_ORIGIN, ACME_EMAIL, and the model"
}

cmd_check() {
  [[ -f "${ENV_FILE}" ]] || fail "no env file at ${ENV_FILE} (deploy/prod.sh init-env creates one)"
  local mode missing=()
  mode="$(stat -c '%a' "${ENV_FILE}" 2>/dev/null || stat -f '%Lp' "${ENV_FILE}")"
  [[ "${mode}" == "600" || "${mode}" == "400" ]] || fail "${ENV_FILE} must be mode 600 (chmod 600 it)"
  for name in "${REQUIRED[@]}"; do [[ -n "$(env_value "${name}")" ]] || missing+=("${name}"); done
  if [[ "${OBS:-0}" == "1" ]]; then
    local grafana
    grafana="$(env_value GRAFANA_ADMIN_PASSWORD)"
    (( ${#grafana} >= 16 )) || missing+=("GRAFANA_ADMIN_PASSWORD (16+ characters)")
  fi
  (( ${#missing[@]} == 0 )) || fail "set these in ${ENV_FILE}: ${missing[*]}"
  [[ "$(env_value PUBLIC_ORIGIN)" == https://* ]] || fail "PUBLIC_ORIGIN must start with https://"
  compose config --quiet
  say "env file and compose file are valid"
}

cmd_build() {
  local tag
  tag="$(git -C "${ROOT}" rev-parse --short=12 HEAD)"
  IMAGE_TAG="${tag}" compose --profile jobs build
  say "built images tagged ${tag}"
}

cmd_up() {
  cmd_check
  local tag
  tag="$(current_tag)"
  docker image inspect "bank-agent-api:${tag}" > /dev/null 2>&1 || fail "no image bank-agent-api:${tag}; run build first"
  compose up -d --wait --remove-orphans
  mkdir -p "${STATE_DIR}"
  if [[ -f "${STATE_DIR}/current" && "$(cat "${STATE_DIR}/current")" != "${tag}" ]]; then
    cp "${STATE_DIR}/current" "${STATE_DIR}/previous"
  fi
  printf '%s' "${tag}" > "${STATE_DIR}/current"
  say "running image tag ${tag}"
}

cmd_seed() {
  compose --profile jobs run --rm seed
}

cmd_backup() {
  mkdir -p "${BACKUP_DIR}"
  chmod 700 "${BACKUP_DIR}"
  local target db
  db="$(env_value POSTGRES_DB)"
  target="${BACKUP_DIR}/bank_agent-$(date -u +%Y%m%dT%H%M%SZ).dump"
  umask 077
  # pg_dump as the bootstrap superuser over the container's local socket (peer authentication): the owner cannot
  # dump tables with forced row-level security, and no password leaves the container.
  compose exec -T postgres pg_dump -U postgres -d "${db:-bank_agent}" --format=custom --no-owner > "${target}"
  [[ -s "${target}" ]] || fail "the backup is empty"
  say "backup written to ${target}"
}

cmd_restore() {
  local source="${1:-}" db
  [[ -f "${source}" ]] || fail "usage: deploy/prod.sh restore <backup file>"
  db="$(env_value POSTGRES_DB)"
  compose stop api purge web
  compose exec -T postgres pg_restore -U postgres -d "${db:-bank_agent}" --clean --if-exists --no-owner \
    --single-transaction --exit-on-error < "${source}"
  compose up -d --wait --remove-orphans
  say "restored ${source}"
}

cmd_update() {
  git -C "${ROOT}" pull --ff-only
  cmd_backup
  cmd_build
  cmd_up
}

cmd_rollback() {
  [[ -f "${STATE_DIR}/previous" ]] || fail "no previous deploy is recorded"
  local previous
  previous="$(cat "${STATE_DIR}/previous")"
  say "rolling back to image tag ${previous}; a rollback across a migration needs deploy/prod.sh restore first"
  IMAGE_TAG="${previous}" cmd_up
}

cmd_purge() {
  compose run --rm migrate bank-agent retention purge
}

cmd_smoke() {
  "${ROOT}/deploy/smoke_test.sh" "$(env_value PUBLIC_ORIGIN)" "$@"
}

cmd_down() {
  compose --profile jobs --profile obs --profile ollama down
}

cmd_destroy() {
  [[ "${1:-}" == "--yes" ]] || fail "this deletes the database and the certificates for good; run: destroy --yes"
  compose --profile jobs --profile obs --profile ollama down --volumes --rmi all
  rm -rf "${STATE_DIR}"
  say "the stack, its volumes, and its images are gone; the backups in ${BACKUP_DIR} and the env file remain"
}

main() {
  local command="${1:-help}"
  shift || true
  case "${command}" in
    init-env) cmd_init_env ;;
    check) cmd_check ;;
    build) cmd_build ;;
    up) cmd_up ;;
    seed) cmd_seed ;;
    update) cmd_update ;;
    backup) cmd_backup ;;
    restore) cmd_restore "$@" ;;
    rollback) cmd_rollback ;;
    purge) cmd_purge ;;
    smoke) cmd_smoke "$@" ;;
    status) compose ps ;;
    logs) compose logs --tail 200 "$@" ;;
    down) cmd_down ;;
    destroy) cmd_destroy "$@" ;;
    *) sed -n '2,21p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' ;;
  esac
}

main "$@"
