#!/usr/bin/env bash
# Run deploy/azure/vm-deploy.sh on the Azure VM through `az vm run-command invoke` (ADR 0038; deploy/README.md,
# "Continuous deployment on Azure"). The deploy workflow calls it after azure/login; an administrator can call it from a
# laptop after `az login`, for example to roll back:
#
#   AZURE_RESOURCE_GROUP=rg-bank-agent AZURE_VM_NAME=vm-bank-agent deploy/azure/run-on-vm.sh rollback
#
# Settings (environment): AZURE_RESOURCE_GROUP and AZURE_VM_NAME (required), VM_CHECKOUT (default
# /home/azureuser/bank-agent); for deploy also DEPLOY_SHA and IMAGE_REGISTRY, and optionally IMAGE_DIGEST_API,
# IMAGE_DIGEST_JOB, IMAGE_DIGEST_WEB, REGISTRY_USER, and REGISTRY_TOKEN.
#
# The settings become `export` lines at the top of a copy of vm-deploy.sh in a mode 600 temporary file, deleted on exit,
# so none of them is a command-line argument here or on the VM. It prints the VM's output (which never holds the token)
# and exits non-zero unless that output ends with vm-deploy's success line, because run-command itself reports success
# whatever the script's exit status.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VM_CHECKOUT="${VM_CHECKOUT:-/home/azureuser/bank-agent}"
SCRIPT=""

say() { printf '%s\n' "$*" >&2; }
fail() {
  say "error: $*"
  exit 1
}

check() {
  # check <name> <value> <pattern>: refuse a malformed setting before it reaches the VM, naming it, never echoing it.
  [[ "$2" =~ $3 ]] || fail "$1 is missing or malformed"
}

main() {
  local action="${1:-}" message
  [[ "${action}" == "deploy" || "${action}" == "rollback" ]] || fail "usage: $0 deploy|rollback"
  command -v az > /dev/null 2>&1 || fail "the Azure CLI (az) is required"
  check AZURE_RESOURCE_GROUP "${AZURE_RESOURCE_GROUP:-}" '^[A-Za-z0-9._()-]{1,90}$'
  check AZURE_VM_NAME "${AZURE_VM_NAME:-}" '^[A-Za-z0-9._-]{1,64}$'
  check VM_CHECKOUT "${VM_CHECKOUT}" '^/[A-Za-z0-9._/-]+$'
  local exports=(DEPLOY_ACTION "${action}" VM_CHECKOUT "${VM_CHECKOUT}")
  if [[ "${action}" == "deploy" ]]; then
    check DEPLOY_SHA "${DEPLOY_SHA:-}" '^[0-9a-f]{40}$'
    check IMAGE_REGISTRY "${IMAGE_REGISTRY:-}" '^[a-z0-9][a-z0-9.-]*(:[0-9]+)?(/[a-z0-9][a-z0-9._-]*)+$'
    local name digest
    for name in API JOB WEB; do
      digest="IMAGE_DIGEST_${name}"
      if [[ -n "${!digest:-}" ]]; then check "${digest}" "${!digest}" '^sha256:[0-9a-f]{64}$'; fi
    done
    if [[ -n "${REGISTRY_TOKEN:-}" ]]; then
      check REGISTRY_USER "${REGISTRY_USER:-}" '^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}(\[bot\])?$'
      [[ "${REGISTRY_TOKEN}" != *[[:space:]]* ]] || fail "REGISTRY_TOKEN is malformed"
    fi
    exports+=(DEPLOY_SHA "${DEPLOY_SHA}" IMAGE_REGISTRY "${IMAGE_REGISTRY}"
      IMAGE_DIGEST_API "${IMAGE_DIGEST_API:-}" IMAGE_DIGEST_JOB "${IMAGE_DIGEST_JOB:-}"
      IMAGE_DIGEST_WEB "${IMAGE_DIGEST_WEB:-}" REGISTRY_USER "${REGISTRY_USER:-}" REGISTRY_TOKEN "${REGISTRY_TOKEN:-}")
  fi

  SCRIPT="$(umask 077 && mktemp)"
  trap 'rm -f -- "${SCRIPT}"' EXIT
  {
    printf '#!/usr/bin/env bash\n'
    printf 'export %s=%q\n' "${exports[@]}"
    tail -n +2 "${HERE}/vm-deploy.sh"
  } > "${SCRIPT}"

  say "running vm-deploy.sh ${action} on ${AZURE_VM_NAME} (${AZURE_RESOURCE_GROUP}) through run-command"
  message="$(az vm run-command invoke --resource-group "${AZURE_RESOURCE_GROUP}" --name "${AZURE_VM_NAME}" \
    --command-id RunShellScript --scripts "@${SCRIPT}" --query 'value[0].message' --output tsv)" ||
    fail "az vm run-command invoke failed (permissions, VM state, or another run-command still running)"
  printf '%s\n' "${message}"
  printf '%s\n' "${message}" | tr -d '\r' | grep -qx "vm-deploy: result=${action}-ok" ||
    fail "vm-deploy.sh did not report success; its log is in /var/log/bank-agent-deploy/ on the VM"
}

main "$@"
