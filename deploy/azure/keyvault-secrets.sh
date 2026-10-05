#!/usr/bin/env bash
# Manage the production secrets in Azure Key Vault from an administrator's machine (ADR 0037; deploy/README.md,
# "Azure VM with Key Vault"). Needs the Azure CLI, a signed-in administrator with Key Vault Secrets Officer on the vault,
# and openssl. Values are generated or typed into a mode 600 temporary file that is deleted at once; no value is ever
# printed or passed as a command-line argument.
#
#   deploy/azure/keyvault-secrets.sh <vault> init            generate every missing generated secret (never overwrites)
#   deploy/azure/keyvault-secrets.sh <vault> set <VARIABLE>  type a provider value, for example LLM_API_KEY_PRIMARY
#                                                            or LANGFUSE_SECRET_KEY
#   deploy/azure/keyvault-secrets.sh <vault> rotate <VARIABLE>  a new random version of SESSION_SECRET, CSRF_SECRET,
#                                                            or GRAFANA_ADMIN_PASSWORD (then deploy/prod.sh rotate)
#   deploy/azure/keyvault-secrets.sh <vault> list            names, enabled, and last update; never values
#
# The names match deploy/secrets_stage.py (a unit test keeps them in step).
set -euo pipefail
export MSYS_NO_PATHCONV=1

# Bash 3.2 compatible (the macOS default shell): no associative arrays.
VARIABLES=(POSTGRES_SUPERUSER_PASSWORD POSTGRES_ADMIN_PASSWORD POSTGRES_APP_PASSWORD SESSION_SECRET CSRF_SECRET
  LLM_API_KEY_PRIMARY LLM_API_KEY_FALLBACK GRAFANA_ADMIN_PASSWORD LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY)
GENERATED=(POSTGRES_SUPERUSER_PASSWORD POSTGRES_ADMIN_PASSWORD POSTGRES_APP_PASSWORD SESSION_SECRET CSRF_SECRET
  GRAFANA_ADMIN_PASSWORD)
ROTATABLE=(SESSION_SECRET CSRF_SECRET GRAFANA_ADMIN_PASSWORD)

say() { printf '%s\n' "$*" >&2; }
fail() { say "error: $*"; exit 1; }

native_path() {
  # The Azure CLI on Windows needs a Windows path; elsewhere the path is unchanged.
  if command -v cygpath > /dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi
}

vault_name_of() {
  # The Key Vault name of a variable: lower case with dashes (SESSION_SECRET -> session-secret).
  [[ " ${VARIABLES[*]} " == *" ${1:-} "* ]] || fail "unknown variable ${1:-} (one of: ${VARIABLES[*]})"
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr '_' '-'
}

VAULT_SECRET_NAMES=""
load_names() {
  # One listing, and a failed listing stops the run: treating an error as "absent" would make init store a new
  # version over a database password that PostgreSQL still holds.
  VAULT_SECRET_NAMES="$(az keyvault secret list --vault-name "${VAULT}" --query "[].name" --output tsv)" ||
    fail "could not list the secrets in ${VAULT}; does your account have Key Vault Secrets Officer on it?"
}

exists() {
  printf '%s\n' "${VAULT_SECRET_NAMES}" | tr -d '\r' | grep -Fxq -- "$1"
}

TEMPORARY=""
cleanup() { if [[ -n "${TEMPORARY}" ]]; then rm -f -- "${TEMPORARY}"; fi; }
trap cleanup EXIT

store_file() {
  # Upload a value file as the secret's new version, then delete the file.
  local name="$1" file="$2"
  [[ -s "${file}" ]] || { rm -f -- "${file}"; fail "refusing to store an empty value for ${name}"; }
  if ! az keyvault secret set --vault-name "${VAULT}" --name "${name}" --file "$(native_path "${file}")" \
    --content-type text/plain --output none; then
    rm -f -- "${file}"
    fail "could not store ${name}; does your account have Key Vault Secrets Officer on ${VAULT}?"
  fi
  rm -f -- "${file}"
  TEMPORARY=""
}

new_value_file() {
  # A fresh 64-character random value in a mode 600 temporary file (printf is a builtin: no argument list exposure).
  # Runs in the caller's shell (not a command substitution), so a failed openssl stops the script under set -e.
  local value
  TEMPORARY="$(umask 077 && mktemp)"
  value="$(openssl rand -hex 32)"
  [[ "${value}" =~ ^[0-9a-f]{64}$ ]] || fail "openssl did not produce a random value"
  printf '%s' "${value}" > "${TEMPORARY}"
}

cmd_init() {
  local variable name created=()
  load_names
  for variable in "${GENERATED[@]}"; do
    name="$(vault_name_of "${variable}")"
    if exists "${name}"; then
      say "${name}: already in the vault, kept"
    else
      new_value_file
      store_file "${name}" "${TEMPORARY}"
      created+=("${name}")
    fi
  done
  say "generated ${#created[@]} secret(s)${created[*]:+: ${created[*]}}"
  say "a hosted model key is typed by its owner: deploy/azure/keyvault-secrets.sh ${VAULT} set LLM_API_KEY_PRIMARY"
}

cmd_set() {
  local variable="${1:-}" name value
  [[ -n "${variable}" ]] || fail "usage: set <VARIABLE>"
  name="$(vault_name_of "${variable}")"
  [[ -t 0 ]] || fail "set reads the value from a terminal; run it interactively"
  read -r -s -p "Value for ${variable} (not shown): " value
  printf '\n' >&2
  [[ -n "${value}" ]] || fail "empty value; nothing stored"
  TEMPORARY="$(umask 077 && mktemp)"
  printf '%s' "${value}" > "${TEMPORARY}"
  value=""
  store_file "${name}" "${TEMPORARY}"
  say "${name}: stored a new version; run deploy/prod.sh rotate on the VM so the services read it"
}

cmd_rotate() {
  local variable="${1:-}" name
  [[ " ${ROTATABLE[*]} " == *" ${variable} "* ]] ||
    fail "rotate covers ${ROTATABLE[*]}; database passwords change inside PostgreSQL first (deploy/README.md)"
  name="$(vault_name_of "${variable}")"
  new_value_file
  store_file "${name}" "${TEMPORARY}"
  say "${name}: stored a new random version; run deploy/prod.sh rotate on the VM"
  [[ "${variable}" == "SESSION_SECRET" ]] && say "SESSION_SECRET changed: every session ends; run deploy/prod.sh seed too"
  return 0
}

cmd_list() {
  az keyvault secret list --vault-name "${VAULT}" \
    --query "[].{name:name, enabled:attributes.enabled, updated:attributes.updated}" --output table
}

main() {
  VAULT="${1:-}"
  local command="${2:-}"
  [[ -n "${VAULT}" && -n "${command}" ]] || { sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 2; }
  command -v az > /dev/null 2>&1 || fail "the Azure CLI (az) is required"
  shift 2
  case "${command}" in
    init) command -v openssl > /dev/null 2>&1 || fail "openssl is required"; cmd_init ;;
    set) cmd_set "$@" ;;
    rotate) command -v openssl > /dev/null 2>&1 || fail "openssl is required"; cmd_rotate "$@" ;;
    list) cmd_list ;;
    *) fail "unknown command ${command}" ;;
  esac
}

main "$@"
