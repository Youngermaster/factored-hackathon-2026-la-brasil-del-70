#!/usr/bin/env bash
# Install the Key Vault secret staging on the Azure VM (ADR 0036; deploy/README.md, "Azure VM with Key Vault").
# Run from the checkout on the VM:
#
#   sudo deploy/azure/install-vm.sh <vault name>
#
# It copies deploy/secrets_stage.py to /usr/local/lib/bank-agent (root-owned, so the boot unit never runs a file from a
# user-writable checkout), records the vault name in /etc/bank-agent/secrets.env (no secret: a name), installs and
# starts bank-agent-secrets.service, and checks the staged files. Run it again after a change to either file.
set -euo pipefail

VAULT="${1:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ "$(id -u)" == "0" ]] || { echo "error: run with sudo" >&2; exit 1; }
[[ "${VAULT}" =~ ^[A-Za-z][A-Za-z0-9-]{1,22}[A-Za-z0-9]$ ]] || { echo "usage: sudo $0 <vault name>" >&2; exit 2; }
command -v python3 > /dev/null 2>&1 || { echo "error: python3 is required" >&2; exit 1; }

install -d -m 0755 -o root -g root /usr/local/lib/bank-agent /etc/bank-agent
install -m 0755 -o root -g root "${HERE}/../secrets_stage.py" /usr/local/lib/bank-agent/secrets_stage.py
printf 'KEY_VAULT_NAME=%s\n' "${VAULT}" > /etc/bank-agent/secrets.env
chmod 0644 /etc/bank-agent/secrets.env
install -m 0644 -o root -g root "${HERE}/bank-agent-secrets.service" /etc/systemd/system/bank-agent-secrets.service
systemctl daemon-reload
systemctl enable bank-agent-secrets.service
systemctl restart bank-agent-secrets.service
python3 /usr/local/lib/bank-agent/secrets_stage.py check --dest /run/bank-agent/secrets
echo "bank-agent-secrets.service is enabled: the secrets are staged now and at every boot, before Docker starts" >&2
