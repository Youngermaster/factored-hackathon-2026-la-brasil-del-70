#!/usr/bin/env bash
# Operate the production stack on one host (deploy/README.md). Run from the repository checkout on the server.
#
#   deploy/prod.sh init-env         create deploy/.env.production from the template (mode 600); with
#                                   SECRETS_SOURCE=keyvault in the environment its secret lines stay empty, else they
#                                   get fresh random values
#   deploy/prod.sh stage-secrets    stage the secrets as files for compose (sudo): from Key Vault or the env file
#   deploy/prod.sh check            validate the env file, the staged secret files (never read), and the compose file
#   deploy/prod.sh build            build the web, api, and job images, tagged with the current git commit
#   deploy/prod.sh pull             instead of build: pull those images from IMAGE_REGISTRY (pushed by the deploy
#                                   workflow under the full commit SHA) and tag them as build would
#   deploy/prod.sh up               stage the secrets, migrate, then start (OBS=1 adds obs, OLLAMA=1 adds ollama)
#   deploy/prod.sh rotate           stage the secrets again and recreate the services, after a new Key Vault version
#   deploy/prod.sh seed             load the demo personas and customers (run once after the first up)
#   deploy/prod.sh update           git pull --ff-only, back up, build, migrate, start
#   deploy/prod.sh release          pull, back up (when the database is running), migrate, start: what continuous
#                                   deployment runs after checking out the commit (deploy/azure/vm-deploy.sh)
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
# tag of the last deploy, else the current commit), SECRETS_NO_CHOWN=1 (a Docker Desktop test host only: staged files
# keep the caller as owner, no sudo). For pull: IMAGE_REGISTRY (or the env file's), IMAGE_DIGEST_API, IMAGE_DIGEST_JOB,
# IMAGE_DIGEST_WEB (pull by digest when set), REGISTRY_USER and REGISTRY_TOKEN_FILE (a file holding a short-lived
# registry token; login happens in a throwaway Docker config that is deleted afterwards). The script never prints a
# secret value.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT}/deploy/.env.production}"
PROJECT="${PROJECT:-bank-agent-prod}"
STATE_DIR="${ROOT}/deploy/.state"
BACKUP_DIR="${BACKUP_DIR:-${ROOT}/deploy/backups}"
STAGER="${ROOT}/deploy/secrets_stage.py"
REQUIRED=(SITE_ADDRESS PUBLIC_ORIGIN)
REQUIRED_SECRETS=(POSTGRES_SUPERUSER_PASSWORD POSTGRES_ADMIN_PASSWORD POSTGRES_APP_PASSWORD SESSION_SECRET CSRF_SECRET)
# The secrets init-env generates, and every secret variable (the model and Langfuse keys come from their providers,
# not from here).
SECRETS=("${REQUIRED_SECRETS[@]}" GRAFANA_ADMIN_PASSWORD)
SECRET_VARIABLES=("${SECRETS[@]}" LLM_API_KEY_PRIMARY LLM_API_KEY_FALLBACK LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY)

say() { printf '%s\n' "$*" >&2; }
fail() { say "error: $*"; exit 1; }

env_value() {
  # The value of $1 in the env file (last assignment wins), without printing it.
  sed -n "s/^$1=//p" "${ENV_FILE}" | tail -n 1
}

secrets_source() {
  local source
  source="$(env_value SECRETS_SOURCE)"
  printf '%s' "${source:-env-file}"
}

secrets_dir() {
  local dir
  dir="$(env_value SECRETS_HOST_DIR)"
  printf '%s' "${dir:-/run/bank-agent/secrets}"
}

as_root() {
  if [[ "$(id -u)" == "0" ]]; then "$@"; else sudo "$@"; fi
}

stager() {
  # The staging script, as root so each file can belong to its container's user, unless SECRETS_NO_CHOWN=1.
  if [[ "${SECRETS_NO_CHOWN:-0}" == "1" ]]; then
    python3 "${STAGER}" "$@" --no-chown
  elif [[ "$1" == "check" ]]; then
    python3 "${STAGER}" "$@"
  else
    as_root python3 "${STAGER}" "$@"
  fi
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
  local source="${SECRETS_SOURCE:-env-file}"
  [[ "${source}" == "keyvault" || "${source}" == "env-file" ]] || fail "SECRETS_SOURCE must be keyvault or env-file"
  umask 077
  local line name
  while IFS= read -r line || [[ -n "${line}" ]]; do
    name="${line%%=*}"
    if [[ "${line}" == "SECRETS_SOURCE=" ]]; then
      printf 'SECRETS_SOURCE=%s\n' "${source}"
    elif [[ "${source}" == "env-file" && "${line}" == *= && " ${SECRETS[*]} " == *" ${name} "* ]]; then
      printf '%s=%s\n' "${name}" "$(openssl rand -hex 32)"
    else
      printf '%s\n' "${line}"
    fi
  done < "${ROOT}/deploy/.env.production.example" > "${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
  if [[ "${source}" == "keyvault" ]]; then
    say "wrote ${ENV_FILE} (mode 600) with no secrets; set KEY_VAULT_NAME, SITE_ADDRESS, PUBLIC_ORIGIN, ACME_EMAIL, and the model"
  else
    say "wrote ${ENV_FILE} (mode 600) with fresh secrets; now set SITE_ADDRESS, PUBLIC_ORIGIN, ACME_EMAIL, and the model"
  fi
}

check_env_file() {
  [[ -f "${ENV_FILE}" ]] || fail "no env file at ${ENV_FILE} (deploy/prod.sh init-env creates one)"
  local mode name missing=() stray=()
  mode="$(stat -c '%a' "${ENV_FILE}" 2>/dev/null || stat -f '%Lp' "${ENV_FILE}")"
  [[ "${mode}" == "600" || "${mode}" == "400" ]] || fail "${ENV_FILE} must be mode 600 (chmod 600 it)"
  for name in "${REQUIRED[@]}"; do [[ -n "$(env_value "${name}")" ]] || missing+=("${name}"); done
  # The Caddyfile's acme snippet is `tls {$ACME_EMAIL}`: an empty address leaves a bare `tls` that Caddy refuses.
  if [[ "$(env_value CADDY_TLS)" != "internal" && -z "$(env_value ACME_EMAIL)" ]]; then
    missing+=("ACME_EMAIL (the certificate authority contact; required unless CADDY_TLS=internal)")
  fi
  case "$(secrets_source)" in
    keyvault)
      [[ -n "$(env_value KEY_VAULT_NAME)" ]] || missing+=(KEY_VAULT_NAME)
      for name in "${SECRET_VARIABLES[@]}"; do [[ -z "$(env_value "${name}")" ]] || stray+=("${name}"); done
      (( ${#stray[@]} == 0 )) ||
        fail "with SECRETS_SOURCE=keyvault these belong in Key Vault; empty them in ${ENV_FILE}: ${stray[*]}"
      ;;
    env-file)
      for name in "${REQUIRED_SECRETS[@]}"; do [[ -n "$(env_value "${name}")" ]] || missing+=("${name}"); done
      if [[ "${OBS:-0}" == "1" ]]; then
        local grafana
        grafana="$(env_value GRAFANA_ADMIN_PASSWORD)"
        (( ${#grafana} >= 16 )) || missing+=("GRAFANA_ADMIN_PASSWORD (16+ characters)")
      fi
      ;;
    *) fail "SECRETS_SOURCE must be keyvault or env-file" ;;
  esac
  (( ${#missing[@]} == 0 )) || fail "set these in ${ENV_FILE}: ${missing[*]}"
  [[ "$(env_value PUBLIC_ORIGIN)" == https://* ]] || fail "PUBLIC_ORIGIN must start with https://"
}

cmd_stage_secrets() {
  check_env_file
  case "$(secrets_source)" in
    keyvault) stager stage --source keyvault --vault "$(env_value KEY_VAULT_NAME)" --dest "$(secrets_dir)" ;;
    env-file) stager stage --source env-file --env-file "${ENV_FILE}" --dest "$(secrets_dir)" ;;
  esac
}

cmd_check() {
  check_env_file
  # Metadata only: the files are root-owned and readable by their container user alone.
  stager check --dest "$(secrets_dir)" || fail "the staged secrets are incomplete; run deploy/prod.sh stage-secrets"
  if [[ "${OBS:-0}" == "1" && ! -s "$(secrets_dir)/grafana/GRAFANA_ADMIN_PASSWORD" ]]; then
    fail "the obs profile needs GRAFANA_ADMIN_PASSWORD (Key Vault secret grafana-admin-password, or the env file)"
  fi
  compose config --quiet
  say "env file, staged secrets, and compose file are valid"
}

cmd_build() {
  local tag
  tag="$(git -C "${ROOT}" rev-parse --short=12 HEAD)"
  IMAGE_TAG="${tag}" compose --profile jobs build
  say "built images tagged ${tag}"
}

IMAGE_NAMES=(api job web)
REGISTRY_PATTERN='^[a-z0-9][a-z0-9.-]*(:[0-9]+)?(/[a-z0-9][a-z0-9._-]*)+$'
DIGEST_PATTERN='^sha256:[0-9a-f]{64}$'

cmd_pull() (
  # A subshell, so the throwaway Docker config and its removal stay local to this command.
  local registry commit tag name ref digest variable config=""
  registry="${IMAGE_REGISTRY:-}"
  if [[ -z "${registry}" && -f "${ENV_FILE}" ]]; then registry="$(env_value IMAGE_REGISTRY)"; fi
  [[ "${registry}" =~ ${REGISTRY_PATTERN} ]] ||
    fail "set IMAGE_REGISTRY to the lower-case image prefix, for example ghcr.io/<owner>/<repository>"
  commit="$(git -C "${ROOT}" rev-parse HEAD)"
  tag="$(git -C "${ROOT}" rev-parse --short=12 HEAD)"
  if [[ -n "${REGISTRY_TOKEN_FILE:-}" ]]; then
    [[ -f "${REGISTRY_TOKEN_FILE}" && -n "${REGISTRY_USER:-}" ]] ||
      fail "REGISTRY_TOKEN_FILE needs REGISTRY_USER and an existing token file"
    config="$(mktemp -d)"
    trap 'rm -rf -- "${config}"' EXIT
    export DOCKER_CONFIG="${config}"
    docker login "${registry%%/*}" --username "${REGISTRY_USER}" --password-stdin < "${REGISTRY_TOKEN_FILE}" > /dev/null
  fi
  for name in "${IMAGE_NAMES[@]}"; do
    variable="IMAGE_DIGEST_$(printf '%s' "${name}" | tr '[:lower:]' '[:upper:]')"
    digest="${!variable:-}"
    if [[ -n "${digest}" ]]; then
      [[ "${digest}" =~ ${DIGEST_PATTERN} ]] || fail "${variable} must look like sha256:<64 hex digits>"
      ref="${registry}/bank-agent-${name}@${digest}"
    else
      ref="${registry}/bank-agent-${name}:${commit}"
    fi
    docker pull --quiet "${ref}" > /dev/null
    docker tag "${ref}" "bank-agent-${name}:${tag}"
    say "pulled ${ref} as bank-agent-${name}:${tag}"
  done
  if [[ -n "${config}" ]]; then docker logout "${registry%%/*}" > /dev/null 2>&1 || true; fi
)

database_running() {
  [[ -n "$(compose ps --status running --quiet postgres 2> /dev/null)" ]]
}

cmd_release() {
  # The pull-by-tag twin of update: the caller has checked out the commit to release.
  cmd_pull
  if database_running; then cmd_backup; else say "no running database to back up (first release)"; fi
  cmd_up
}

cmd_up() {
  cmd_stage_secrets
  cmd_check
  local tag
  tag="$(current_tag)"
  docker image inspect "bank-agent-api:${tag}" > /dev/null 2>&1 || fail "no image bank-agent-api:${tag}; run build first"
  compose up -d --wait --remove-orphans "$@"
  mkdir -p "${STATE_DIR}"
  if [[ -f "${STATE_DIR}/current" && "$(cat "${STATE_DIR}/current")" != "${tag}" ]]; then
    cp "${STATE_DIR}/current" "${STATE_DIR}/previous"
  fi
  printf '%s' "${tag}" > "${STATE_DIR}/current"
  say "running image tag ${tag}"
}

cmd_rotate() {
  # Compose bind-mounts each file, and a running container keeps the version it started with: recreate them all.
  say "staging the current Key Vault (or env file) versions and recreating every service"
  cmd_up --force-recreate
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
  compose exec -T postgres pg_dump -U postgres -d "${db:-bank_agent}" --format=custom > "${target}"
  [[ -s "${target}" ]] || fail "the backup is empty"
  say "backup written to ${target}"
}

cmd_restore() {
  local source="${1:-}" db
  [[ -f "${source}" ]] || fail "usage: deploy/prod.sh restore <backup file>"
  db="$(env_value POSTGRES_DB)"
  compose stop api purge web
  compose exec -T postgres pg_restore -U postgres -d "${db:-bank_agent}" --clean --if-exists \
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
  local dir
  dir="$(secrets_dir)"
  # Only the stager's own consumer directories, never whatever SECRETS_HOST_DIR happens to point at.
  as_root rm -rf -- "${dir}/app" "${dir}/postgres" "${dir}/grafana"
  say "the stack, its volumes, its images, and the staged secrets are gone; the backups in ${BACKUP_DIR} and the env file remain"
}

main() {
  local command="${1:-help}"
  shift || true
  case "${command}" in
    init-env) cmd_init_env ;;
    stage-secrets) cmd_stage_secrets ;;
    check) cmd_check ;;
    build) cmd_build ;;
    pull) cmd_pull ;;
    release) cmd_release ;;
    up) cmd_up ;;
    rotate) cmd_rotate ;;
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
    *) sed -n '2,32p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' ;;
  esac
}

main "$@"
