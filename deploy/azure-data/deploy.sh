#!/usr/bin/env bash
# Provision and run only the authorized Azure data environment. Never copies a local env file.
set +x
set -euo pipefail
umask 077
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."

subscription=32847dfa-5fd4-4276-8bdf-243d72b35119
tenant=4a5e7334-7901-444c-964b-3e6100209fd1
group=rg-la70-test
vm='vm-la70-data'
state=data/azure-data
mkdir -p "$state"
storage="stla70$(printf '%s' "$subscription/$group" | sha256sum | cut -c1-16)"
az_args=(--subscription "$subscription" --only-show-errors)
[[ "$(az account show --query tenantId -o tsv)" == "$tenant" ]] || { printf 'Wrong tenant.\n' >&2; exit 2; }
[[ "$(az account show "${az_args[@]}" --query user.name -o tsv)" == valenciajuliann@hotmail.com ]] || {
    printf 'Wrong operator account.\n' >&2; exit 2;
}
[[ "$(az group show -n "$group" "${az_args[@]}" --query location -o tsv)" == eastus2 ]] || exit 2

invoke() {
    az vm run-command invoke -g "$group" -n "$vm" --command-id RunShellScript \
        --scripts "@$1" "${az_args[@]}" --query 'value[].message' -o tsv
}

case "${1:-}" in
    validate|provision|validate-storage|provision-storage)
        if [[ ! -f "$state/ssh.pub" ]]; then
            ssh-keygen -q -t ed25519 -N '' -f "$state/bootstrap-key"
            cp "$state/bootstrap-key.pub" "$state/ssh.pub"
            # There is no SSH ingress; discard the unused private key immediately.
            python3 - "$state" <<'PY'
import sys
from pathlib import Path
root = Path(sys.argv[1])
(root / 'bootstrap-key').unlink()
(root / 'bootstrap-key.pub').unlink()
PY
        fi
        operator=$(az ad signed-in-user show --query id -o tsv)
        parameters=("storageName=$storage" "operatorId=$operator" "sshPublicKey=$(cat "$state/ssh.pub")")
        if [[ "$1" == *-storage ]]; then parameters+=(deployVm=false); fi
        az deployment group validate -g "$group" -n la70-data \
            --template-file deploy/azure-data/main.json --parameters "${parameters[@]}" \
            "${az_args[@]}" --query properties.provisioningState -o tsv
        if [[ "$1" == provision* ]]; then
            az deployment group create -g "$group" -n la70-data \
                --template-file deploy/azure-data/main.json --parameters "${parameters[@]}" \
                "${az_args[@]}" --query properties.provisioningState -o tsv
        fi
        ;;
    release)
        revision=$(git rev-parse HEAD)
        git archive --format=tar.gz --output="$state/$revision.tar.gz" "$revision"
        digest=$(sha256sum "$state/$revision.tar.gz" | cut -d' ' -f1)
        az storage blob upload --account-name "$storage" --container-name artifacts \
            --name "releases/$digest.tar.gz" --file "$state/$revision.tar.gz" --auth-mode login \
            --overwrite false --only-show-errors -o none
        printf '%s %s\n' "$revision" "$digest" > "$state/release"
        printf 'Uploaded committed revision %s with SHA-256 %s.\n' "$revision" "$digest"
        ;;
    start)
        read -r revision digest < "$state/release"
        [[ "$revision" =~ ^[0-9a-f]{40}$ && "$digest" =~ ^[0-9a-f]{64}$ ]] || exit 2
        source_kind=${2:-sample}
        case "$source_kind" in sample|local|s3) ;; *) exit 2 ;; esac
        # Python transfer code is supplied as code, never with an access token or SAS.
        {
            printf 'set -eu\numask 077\nmkdir -p /opt/la70-data\n'
            printf "cat > /opt/la70-data/blob.py <<'LA70_BLOB_PY'\n"
            git show "$revision:deploy/azure-data/blob.py"
            printf 'LA70_BLOB_PY\n'
            printf 'python3 /opt/la70-data/blob.py download %s releases/%s.tar.gz /opt/la70-data/release.tar.gz --sha256 %s\n' "$storage" "$digest" "$digest"
            printf 'mkdir -p /opt/la70-data/releases/%s\n' "$revision"
            printf 'tar -xzf /opt/la70-data/release.tar.gz -C /opt/la70-data/releases/%s\n' "$revision"
            printf 'cd /opt/la70-data/releases/%s\nbash deploy/azure-data/bootstrap.sh > /opt/la70-data/bootstrap.log 2>&1\n' "$revision"
            # No inbound port is needed. systemd gives the pipeline an independently inspectable handle.
            printf 'systemd-run --unit=la70-data-pipeline --collect bash /opt/la70-data/releases/%s/deploy/azure-data/run.sh %s %s\n' "$revision" "$revision" "$source_kind"
        } > "$state/start.sh"
        invoke "$state/start.sh"
        ;;
    status)
        cat > "$state/status.sh" <<'SH'
set -eu
root=/opt/la70-data
if [ ! -f "$root/latest-run" ]; then
    systemctl show la70-data-pipeline --property=ActiveState,SubState,Result
    exit 0
fi
run=$(cat "$root/latest-run")
cat "$root/runs/$run/status"
if [ -f "$root/runs/$run/result.json" ]; then cat "$root/runs/$run/result.json"; fi
systemctl show la70-data-pipeline --property=ActiveState,SubState,Result
SH
        invoke "$state/status.sh"
        ;;
    publish)
        {
            printf 'storage=%s\n' "$storage"
            cat <<'SH'
set -eu
umask 077
root=/opt/la70-data
run=$(cat "$root/latest-run")
test "$(cat "$root/runs/$run/status")" != running
tar -czf "$root/runs/$run.tar.gz" -C "$root/runs" "$run"
digest=$(sha256sum "$root/runs/$run.tar.gz" | cut -d" " -f1)
python3 "$root/blob.py" upload "$storage" "runs/$digest.tar.gz" "$root/runs/$run.tar.gz"
python3 "$root/blob.py" upload "$storage" "runs/$run/result.json" "$root/runs/$run/result.json"
printf 'Published run %s artifact SHA-256 %s\n' "$run" "$digest"
SH
        } > "$state/publish.sh"
        invoke "$state/publish.sh"
        ;;
    *) printf 'Usage: %s validate|provision|provision-storage|release|start [sample|local|s3]|status|publish\n' "$0" >&2; exit 2 ;;
esac
