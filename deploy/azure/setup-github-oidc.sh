#!/usr/bin/env bash
# One-time setup of the Azure identity the deploy workflow signs in with (ADR 0038; deploy/README.md, "Continuous
# deployment on Azure"). Run it once from an administrator's machine after `az login`, after deploy/azure/provision.sh
# created the resource group and the VM. Every step is idempotent: run it again to finish an interrupted run or to
# check that everything is still in place. It creates no client secret, certificate, or password.
#
#   deploy/azure/setup-github-oidc.sh --dry-run     # print what it would create; works without az or a sign-in
#   deploy/azure/setup-github-oidc.sh               # create or reuse, then print the GitHub settings
#
# Settings (environment):
#   SUBJECT_PREFIX      the token subject prefix; default asked from GitHub (actions/oidc/customization/sub), which
#                       includes immutable ids ("repo:owner@<id>/name@<id>") on repositories that use them
#   GITHUB_REPOSITORY   owner/name exactly as GitHub spells it (the federated subject is case-sensitive); default
#                       from `gh repo view`, else the origin remote
#   RESOURCE_GROUP      default rg-bank-agent;  VM_NAME  default vm-bank-agent (as in provision.sh)
#   APP_NAME            the Entra app registration; default github-deploy-<repository name>
#   ENVIRONMENT         the GitHub environment the deploy jobs use; default production
#   BRANCH_CREDENTIAL   1 (default) also trusts refs/heads/main outside any environment; 0 skips it (the workflow
#                       never needs it, and every trusted subject is one more way to obtain the identity)
#   ROLE_MODE           custom (default): a role that allows only run-command and reading the VM, assigned on the VM;
#                       builtin: Virtual Machine Contributor on the resource group (if a tenant forbids custom roles)
#   PUBLIC_URL          default https://<the VM's public DNS name>
#   VM_CHECKOUT         the checkout on the VM; default /home/azureuser/bank-agent
#
# Key Vault access stays with the VM's managed identity (ADR 0037): this identity gets no Key Vault role. The values it
# prints are identifiers, not secrets; it never prints a token.
set -euo pipefail
export MSYS_NO_PATHCONV=1

DRY_RUN=0
for argument in "$@"; do
  case "${argument}" in
    --dry-run) DRY_RUN=1 ;;
    -h | --help) sed -n '2,24p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) printf 'error: unknown argument %s (try --help)\n' "${argument}" >&2; exit 2 ;;
  esac
done

RESOURCE_GROUP="${RESOURCE_GROUP:-rg-bank-agent}"
VM_NAME="${VM_NAME:-vm-bank-agent}"
ENVIRONMENT="${ENVIRONMENT:-production}"
BRANCH_CREDENTIAL="${BRANCH_CREDENTIAL:-1}"
ROLE_MODE="${ROLE_MODE:-custom}"
VM_CHECKOUT="${VM_CHECKOUT:-/home/azureuser/bank-agent}"
CUSTOM_ROLE="Bank Agent deploy (run-command only)"
ISSUER="https://token.actions.githubusercontent.com"
AUDIENCE="api://AzureADTokenExchange"
ONLINE=1
WORK="$(mktemp -d)"
trap 'rm -rf -- "${WORK}"' EXIT

say() { printf '%s\n' "$*" >&2; }
fail() {
  say "error: $*"
  exit 1
}

run() {
  # A command that changes something: printed (never executed) in a dry run.
  if [[ "${DRY_RUN}" == "1" ]]; then
    say "dry-run: $(printf '%q ' "$@")"
  else
    "$@"
  fi
}

query() {
  # A read-only az query; offline dry runs answer nothing, as if the object did not exist yet.
  if [[ "${ONLINE}" == "1" ]]; then az "$@"; fi
}

repository() {
  local url
  if [[ -n "${GITHUB_REPOSITORY:-}" ]]; then printf '%s' "${GITHUB_REPOSITORY}"; return; fi
  if command -v gh > /dev/null 2>&1 && gh repo view --json nameWithOwner --jq .nameWithOwner 2> /dev/null; then return; fi
  url="$(git -C "$(dirname "${BASH_SOURCE[0]}")" remote get-url origin 2> /dev/null || true)"
  url="${url%.git}"
  printf '%s' "${url}" | sed -E 's#^(git@github\.com:|https://github\.com/)##'
}

subject_prefix() {
  # GitHub can put immutable owner and repository ids in the token subject ("repo:owner@<id>/name@<id>"), and new
  # repositories do so by default. The federated subject must match exactly, so ask GitHub for the prefix it uses.
  local prefix=""
  if [[ -n "${SUBJECT_PREFIX:-}" ]]; then printf '%s' "${SUBJECT_PREFIX}"; return; fi
  # gh prints the error body on stdout when the call fails, so keep its output only when it succeeds.
  if command -v gh > /dev/null 2>&1 &&
    prefix="$(gh api "repos/${REPOSITORY}/actions/oidc/customization/sub" --jq '.sub_claim_prefix // empty' 2> /dev/null)"; then
    :
  else
    prefix=""
  fi
  printf '%s' "${prefix:-repo:${REPOSITORY}}"
}

REPOSITORY="$(repository)"
[[ "${REPOSITORY}" =~ ^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$ ]] || fail "set GITHUB_REPOSITORY=owner/name"
SUB_PREFIX="$(subject_prefix)"
[[ "${SUB_PREFIX}" =~ ^repo:[A-Za-z0-9@._/-]+$ ]] || fail "unexpected subject prefix; set SUBJECT_PREFIX=repo:owner/name"
APP_NAME="${APP_NAME:-github-deploy-${REPOSITORY#*/}}"
[[ "${ROLE_MODE}" == "custom" || "${ROLE_MODE}" == "builtin" ]] || fail "ROLE_MODE must be custom or builtin"
[[ "${ENVIRONMENT}" =~ ^[A-Za-z0-9._-]+$ ]] || fail "ENVIRONMENT must be a plain environment name"

if ! command -v az > /dev/null 2>&1 || ! az account show --output none 2> /dev/null; then
  [[ "${DRY_RUN}" == "1" ]] || fail "the Azure CLI must be installed and signed in (az login)"
  ONLINE=0
  say "dry run without a signed-in Azure CLI: every object is shown as missing, ids as placeholders"
fi

placeholder() { printf '<%s>' "$1"; }

say "1/6 subscription, tenant, resource group ${RESOURCE_GROUP}, and VM ${VM_NAME}"
SUBSCRIPTION_ID="$(query account show --query id --output tsv)"
TENANT_ID="$(query account show --query tenantId --output tsv)"
GROUP_ID="$(query group show --name "${RESOURCE_GROUP}" --query id --output tsv 2> /dev/null || true)"
VM_ID="$(query vm show --resource-group "${RESOURCE_GROUP}" --name "${VM_NAME}" --query id --output tsv 2> /dev/null || true)"
if [[ "${ONLINE}" == "1" && ( -z "${GROUP_ID}" || -z "${VM_ID}" ) ]]; then
  fail "no VM ${VM_NAME} in ${RESOURCE_GROUP}; run deploy/azure/provision.sh first (or set RESOURCE_GROUP and VM_NAME)"
fi
SUBSCRIPTION_ID="${SUBSCRIPTION_ID:-$(placeholder subscription-id)}"
TENANT_ID="${TENANT_ID:-$(placeholder tenant-id)}"
GROUP_ID="${GROUP_ID:-/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}}"
VM_ID="${VM_ID:-${GROUP_ID}/providers/Microsoft.Compute/virtualMachines/${VM_NAME}}"

say "2/6 app registration ${APP_NAME} (no secret, no certificate)"
APP_ID="$(query ad app list --display-name "${APP_NAME}" --query "[0].appId" --output tsv)"
if [[ -z "${APP_ID}" ]]; then
  if [[ "${DRY_RUN}" == "1" ]]; then
    run az ad app create --display-name "${APP_NAME}" --sign-in-audience AzureADMyOrg
    APP_ID="$(placeholder app-client-id)"
  else
    APP_ID="$(az ad app create --display-name "${APP_NAME}" --sign-in-audience AzureADMyOrg --query appId --output tsv)"
    say "    created"
  fi
else
  say "    reused"
fi

say "3/6 service principal"
SP_ID=""
if [[ "${APP_ID}" != \<* ]]; then
  SP_ID="$(query ad sp list --filter "appId eq '${APP_ID}'" --query "[0].id" --output tsv)"
fi
if [[ -z "${SP_ID}" ]]; then
  if [[ "${DRY_RUN}" == "1" ]]; then
    run az ad sp create --id "${APP_ID}"
    SP_ID="$(placeholder service-principal-object-id)"
  else
    SP_ID="$(az ad sp create --id "${APP_ID}" --query id --output tsv)"
    say "    created"
  fi
else
  say "    reused"
fi

say "4/6 federated credentials for ${REPOSITORY}"
federate() {
  # federate <name> <subject>: create the credential, or update it when its subject changed (a renamed repository).
  local name="$1" subject="$2" file="${WORK}/$1.json" current=""
  printf '{"name":"%s","issuer":"%s","subject":"%s","audiences":["%s"],"description":"%s"}\n' \
    "${name}" "${ISSUER}" "${subject}" "${AUDIENCE}" "GitHub Actions OIDC for ${REPOSITORY}" > "${file}"
  if [[ "${APP_ID}" != \<* ]]; then
    current="$(query ad app federated-credential list --id "${APP_ID}" --query "[?name=='${name}'].subject | [0]" \
      --output tsv)"
  fi
  if [[ "${current}" == "${subject}" ]]; then
    say "    ${name}: ${subject} (in place)"
  elif [[ -z "${current}" ]]; then
    run az ad app federated-credential create --id "${APP_ID}" --parameters "@${file}" --output none
    say "    ${name}: ${subject}"
  else
    run az ad app federated-credential update --id "${APP_ID}" --federated-credential-id "${name}" \
      --parameters "@${file}" --output none
    say "    ${name}: subject updated to ${subject}"
  fi
}
federate "github-${ENVIRONMENT}-environment" "${SUB_PREFIX}:environment:${ENVIRONMENT}"
if [[ "${BRANCH_CREDENTIAL}" == "1" ]]; then
  federate "github-main-branch" "${SUB_PREFIX}:ref:refs/heads/main"
else
  say "    github-main-branch: skipped (BRANCH_CREDENTIAL=0)"
fi

say "5/6 least-privilege role (${ROLE_MODE})"
if [[ "${ROLE_MODE}" == "custom" ]]; then
  ROLE="${CUSTOM_ROLE}"
  SCOPE="${VM_ID}"
  printf '{"Name":"%s","IsCustom":true,"Description":"%s","Actions":["%s","%s"],"NotActions":[],"AssignableScopes":["%s"]}\n' \
    "${CUSTOM_ROLE}" "Run commands on the bank-agent VM and read it; nothing else (deploy workflow, ADR 0038)" \
    "Microsoft.Compute/virtualMachines/read" "Microsoft.Compute/virtualMachines/runCommand/action" "${GROUP_ID}" \
    > "${WORK}/role.json"
  if [[ -z "$(query role definition list --name "${CUSTOM_ROLE}" --custom-role-only true --query "[0].id" --output tsv)" ]]; then
    run az role definition create --role-definition "@${WORK}/role.json" --output none
    say "    role definition: new (Azure may take a minute to make it assignable)"
  else
    run az role definition update --role-definition "@${WORK}/role.json" --output none
    say "    role definition in place (actions and scope refreshed)"
  fi
else
  ROLE="Virtual Machine Contributor"
  SCOPE="${GROUP_ID}"
fi
EXISTING=""
if [[ "${SP_ID}" != \<* ]]; then
  EXISTING="$(query role assignment list --assignee "${SP_ID}" --scope "${SCOPE}" --role "${ROLE}" --query "[0].id" \
    --output tsv 2> /dev/null || true)"
fi
if [[ -n "${EXISTING}" ]]; then
  say "    ${ROLE} on ${SCOPE##*/}: in place"
elif [[ "${DRY_RUN}" == "1" ]]; then
  run az role assignment create --assignee-object-id "${SP_ID}" --assignee-principal-type ServicePrincipal \
    --role "${ROLE}" --scope "${SCOPE}" --output none
else
  # A new service principal or custom role takes a while to replicate; retry for about two minutes.
  for attempt in 1 2 3 4 5 6 7 8; do
    if az role assignment create --assignee-object-id "${SP_ID}" --assignee-principal-type ServicePrincipal \
      --role "${ROLE}" --scope "${SCOPE}" --output none 2> "${WORK}/assign.err"; then
      say "    ${ROLE} on ${SCOPE##*/}: assigned"
      break
    fi
    (( attempt < 8 )) || { cat "${WORK}/assign.err" >&2; fail "could not assign ${ROLE}; run this script again later"; }
    say "    waiting for Azure to replicate the role or the identity (attempt ${attempt})"
    sleep 15
  done
fi
if [[ "${ROLE_MODE}" == "custom" && "${SP_ID}" != \<* ]]; then
  LEFTOVER="$(query role assignment list --assignee "${SP_ID}" --scope "${GROUP_ID}" --role "Virtual Machine Contributor" \
    --query "[0].id" --output tsv 2> /dev/null || true)"
  [[ -z "${LEFTOVER}" ]] ||
    say "    note: an earlier Virtual Machine Contributor grant on ${RESOURCE_GROUP} remains; remove it to keep only run-command"
fi

say "6/6 the values for GitHub"
FQDN="$(query network public-ip show --resource-group "${RESOURCE_GROUP}" --name "${VM_NAME}PublicIP" \
  --query dnsSettings.fqdn --output tsv 2> /dev/null || true)"
PUBLIC_URL="${PUBLIC_URL:-https://${FQDN:-$(placeholder vm-public-dns-name)}}"
cat << SUMMARY

Environment secrets of the GitHub environment "${ENVIRONMENT}" (identifiers, not credentials; secrets only so that
jobs outside the environment never see them). Settings, Environments, ${ENVIRONMENT}, Environment secrets:
  AZURE_CLIENT_ID        ${APP_ID}
  AZURE_TENANT_ID        ${TENANT_ID}
  AZURE_SUBSCRIPTION_ID  ${SUBSCRIPTION_ID}

Repository variables. Settings, Secrets and variables, Actions, Variables:
  AZURE_RESOURCE_GROUP   ${RESOURCE_GROUP}
  AZURE_VM_NAME          ${VM_NAME}
  PUBLIC_URL             ${PUBLIC_URL}
  VM_CHECKOUT            ${VM_CHECKOUT}
  VITE_DEMO_MODE         true   (the public judging demo; false otherwise)
  DEPLOY_ENABLED         true   (last: after a manual run of the deploy workflow passed)

The same with the GitHub CLI (gh auth login first):
  gh api --method PUT repos/${REPOSITORY}/environments/${ENVIRONMENT} > /dev/null
  gh secret set AZURE_CLIENT_ID --repo ${REPOSITORY} --env ${ENVIRONMENT} --body '${APP_ID}'
  gh secret set AZURE_TENANT_ID --repo ${REPOSITORY} --env ${ENVIRONMENT} --body '${TENANT_ID}'
  gh secret set AZURE_SUBSCRIPTION_ID --repo ${REPOSITORY} --env ${ENVIRONMENT} --body '${SUBSCRIPTION_ID}'
  gh variable set AZURE_RESOURCE_GROUP --repo ${REPOSITORY} --body '${RESOURCE_GROUP}'
  gh variable set AZURE_VM_NAME --repo ${REPOSITORY} --body '${VM_NAME}'
  gh variable set PUBLIC_URL --repo ${REPOSITORY} --body '${PUBLIC_URL}'
  gh variable set VM_CHECKOUT --repo ${REPOSITORY} --body '${VM_CHECKOUT}'
  gh variable set VITE_DEMO_MODE --repo ${REPOSITORY} --body 'true'

Then, in Settings, Environments, ${ENVIRONMENT}: add yourself as a required reviewer and limit deployment branches to
main. Run the workflow once by hand (Actions, deploy, Run workflow), and set DEPLOY_ENABLED=true when it passes.
SUMMARY
if [[ "${DRY_RUN}" == "1" ]]; then say "dry run: nothing was created or changed"; fi
