#!/usr/bin/env bash
# Create the Azure resources for the production stack (ADR 0036; deploy/README.md, "Azure VM with Key Vault"), from an
# administrator's machine with the Azure CLI signed in (`az login`). Every step is idempotent: run it again to finish an
# interrupted run. It creates no credential for the application: the VM reads Key Vault with its managed identity.
#
#   VAULT_NAME=kv-bank-agent-x DNS_LABEL=bank-agent-x SSH_SOURCE_CIDR=203.0.113.7/32 deploy/azure/provision.sh
#
# Settings (environment):
#   VAULT_NAME        required; globally unique, 3 to 24 letters, digits, or dashes
#   DNS_LABEL         required; the site becomes <DNS_LABEL>.<LOCATION>.cloudapp.azure.com (SITE_ADDRESS)
#   SSH_SOURCE_CIDR   required; the only address allowed to reach SSH, for example your public IP with /32
#   LOCATION          default westus2;      RESOURCE_GROUP  default rg-bank-agent
#   VM_NAME           default vm-bank-agent; VM_SIZE        default Standard_B2als_v2 (2 vCPU, 4 GB)
#   ADMIN_USER        default azureuser;     SSH_PUBLIC_KEY  default ~/.ssh/azure_bank_agent.pub
#   DISK_GB           default 40;           VM_IMAGE      default Canonical:ubuntu-24_04-lts:server:latest
#
# Steps: resource group; Key Vault (RBAC, soft delete 7 days); Key Vault Secrets Officer for you on that vault only;
# the generated secrets (deploy/azure/keyvault-secrets.sh init); the VM (Ubuntu 24.04, system-assigned identity, a
# Standard static public IP with the DNS label); firewall rules (SSH from SSH_SOURCE_CIDR, HTTP and HTTPS from
# anywhere); Key Vault Secrets User for the VM identity on each application secret that exists, and nothing else.
set -euo pipefail
export MSYS_NO_PATHCONV=1

: "${VAULT_NAME:?set VAULT_NAME}"
: "${DNS_LABEL:?set DNS_LABEL}"
: "${SSH_SOURCE_CIDR:?set SSH_SOURCE_CIDR (your public IP followed by /32)}"
LOCATION="${LOCATION:-westus2}"
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-bank-agent}"
VM_NAME="${VM_NAME:-vm-bank-agent}"
VM_SIZE="${VM_SIZE:-Standard_B2als_v2}"
ADMIN_USER="${ADMIN_USER:-azureuser}"
SSH_PUBLIC_KEY="${SSH_PUBLIC_KEY:-${HOME}/.ssh/azure_bank_agent.pub}"
DISK_GB="${DISK_GB:-40}"
# The full image URN, not the "Ubuntu2404" alias: the alias list is downloaded at run time and a network hiccup breaks it.
VM_IMAGE="${VM_IMAGE:-Canonical:ubuntu-24_04-lts:server:latest}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_SECRETS=(postgres-superuser-password postgres-admin-password postgres-app-password session-secret csrf-secret
  llm-api-key-primary llm-api-key-fallback grafana-admin-password)

say() { printf '%s\n' "$*" >&2; }
fail() { say "error: $*"; exit 1; }

command -v az > /dev/null 2>&1 || fail "the Azure CLI (az) is required"
[[ -f "${SSH_PUBLIC_KEY}" ]] || fail "no SSH public key at ${SSH_PUBLIC_KEY} (ssh-keygen -t ed25519 -f ${SSH_PUBLIC_KEY%.pub})"
[[ "${SSH_SOURCE_CIDR}" =~ ^[0-9.]+/[0-9]+$ ]] || fail "SSH_SOURCE_CIDR must look like 203.0.113.7/32"

say "1/7 resource group ${RESOURCE_GROUP} in ${LOCATION}"
az group create --name "${RESOURCE_GROUP}" --location "${LOCATION}" --output none

say "2/7 Key Vault ${VAULT_NAME} (RBAC authorization, soft delete 7 days)"
if ! az keyvault show --name "${VAULT_NAME}" --output none 2> /dev/null; then
  az keyvault create --name "${VAULT_NAME}" --resource-group "${RESOURCE_GROUP}" --location "${LOCATION}" \
    --enable-rbac-authorization true --retention-days 7 --output none
fi
VAULT_ID="$(az keyvault show --name "${VAULT_NAME}" --query id --output tsv)"

say "3/7 Key Vault Secrets Officer for the signed-in administrator on this vault only"
ADMIN_ID="$(az ad signed-in-user show --query id --output tsv)"
if [[ -z "$(az role assignment list --assignee "${ADMIN_ID}" --scope "${VAULT_ID}" \
  --role "Key Vault Secrets Officer" --query "[0].id" --output tsv)" ]]; then
  az role assignment create --assignee-object-id "${ADMIN_ID}" --assignee-principal-type User \
    --role "Key Vault Secrets Officer" --scope "${VAULT_ID}" --output none
  say "    waiting 60 seconds for the role to apply"
  sleep 60
fi

say "4/7 generated secrets"
"${HERE}/keyvault-secrets.sh" "${VAULT_NAME}" init

say "5/7 VM ${VM_NAME} (${VM_SIZE}, Ubuntu 24.04, system-assigned identity, static IP ${DNS_LABEL})"
if ! az vm show --resource-group "${RESOURCE_GROUP}" --name "${VM_NAME}" --output none 2> /dev/null; then
  az vm create --resource-group "${RESOURCE_GROUP}" --name "${VM_NAME}" --location "${LOCATION}" \
    --image "${VM_IMAGE}" --size "${VM_SIZE}" --admin-username "${ADMIN_USER}" \
    --ssh-key-values "$(cat "${SSH_PUBLIC_KEY}")" --assign-identity \
    --public-ip-sku Standard --public-ip-address-allocation static --public-ip-address-dns-name "${DNS_LABEL}" \
    --nsg "${VM_NAME}-nsg" --nsg-rule NONE --storage-sku StandardSSD_LRS --os-disk-size-gb "${DISK_GB}" \
    --output none
fi

say "6/7 firewall: SSH from ${SSH_SOURCE_CIDR} only, HTTP and HTTPS (TCP and UDP 443) from anywhere"
rule() {
  az network nsg rule create --resource-group "${RESOURCE_GROUP}" --nsg-name "${VM_NAME}-nsg" --name "$1" \
    --priority "$2" --protocol "$3" --destination-port-ranges "$4" --source-address-prefixes "$5" \
    --access Allow --direction Inbound --output none
}
rule allow-ssh-admin 100 Tcp 22 "${SSH_SOURCE_CIDR}"
rule allow-http 110 Tcp 80 '*'
rule allow-https 120 Tcp 443 '*'
rule allow-http3 130 Udp 443 '*'

say "7/7 Key Vault Secrets User for the VM identity, per application secret"
PRINCIPAL_ID="$(az vm show --resource-group "${RESOURCE_GROUP}" --name "${VM_NAME}" \
  --query identity.principalId --output tsv)"
for name in "${APP_SECRETS[@]}"; do
  if az keyvault secret show --vault-name "${VAULT_NAME}" --name "${name}" --query id --output tsv > /dev/null 2>&1; then
    az role assignment create --assignee-object-id "${PRINCIPAL_ID}" --assignee-principal-type ServicePrincipal \
      --role "Key Vault Secrets User" --scope "${VAULT_ID}/secrets/${name}" --output none
    say "    ${name}: readable by the VM"
  else
    say "    ${name}: not in the vault yet (optional); run this script again after setting it"
  fi
done

FQDN="$(az network public-ip show --resource-group "${RESOURCE_GROUP}" --name "${VM_NAME}PublicIP" \
  --query dnsSettings.fqdn --output tsv 2> /dev/null || true)"
say ""
say "done. SITE_ADDRESS=${FQDN:-${DNS_LABEL}.${LOCATION}.cloudapp.azure.com}"
say "next: ssh -i ${SSH_PUBLIC_KEY%.pub} ${ADMIN_USER}@${FQDN:-<the VM address>}, then follow deploy/README.md"
