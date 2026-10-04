"""Prepare an isolated Azure naming migration and verify every copied artifact before VM replacement."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SUBSCRIPTION = "32847dfa-5fd4-4276-8bdf-243d72b35119"
TENANT = "4a5e7334-7901-444c-964b-3e6100209fd1"
SOURCE_GROUP = "rg-bank-agent"
SOURCE_VM = "vm-bank-database"
SOURCE_STORAGE = "stla70238253ae46a02964"
GROUP = "rg-data-engineering-test"
VM = "vm-data-engineering-database"
STORAGE = "stdataeng213c0ee90850"
DISK = "disk-data-engineering-database-os"
SNAPSHOT = "snap-data-engineering-database-20261004"
STATE = Path("data/data-engineering")
PACKAGE = Path(__file__).resolve().parent
PUBLIC_ERROR_CODES = {
    "AuthorizationFailed",
    "InvalidTemplate",
    "InvalidTemplateDeployment",
    "DeploymentFailed",
    "ResourceNotFound",
    "ResourceNotAvailableForOffer",
    "StorageAccountAlreadyTaken",
    "OperationNotAllowed",
    "InvalidParameter",
    "ResourceGroupNotFound",
    "QuotaExceeded",
    "Conflict",
}


class CloudOperationError(RuntimeError):
    """Only a command category and whitelisted Azure error code, never raw diagnostics."""


class MigrationValidationError(ValueError):
    """A fixed migration validation message containing no input values or credentials."""


def run(arguments: list[str], payload: bytes | None = None) -> bytes:
    result = subprocess.run(arguments, input=payload, capture_output=True, check=False)
    if result.returncode:
        code = re.search(r"\(([A-Za-z][A-Za-z0-9]{1,80})\)", result.stderr.decode(errors="replace"))
        category = "Azure operation"
        label = code.group(1) if code and code.group(1) in PUBLIC_ERROR_CODES else "OperationFailed"
        raise CloudOperationError(f"{category}: {label}")
    return result.stdout


def az(*arguments: str) -> Any:
    scope = [] if arguments[:1] == ("ad",) else ["--subscription", SUBSCRIPTION]
    raw = run(["az", *arguments, *scope, "--only-show-errors", "-o", "json"])
    return json.loads(raw) if raw.strip() else None


def guard() -> None:
    current = json.loads(run(["az", "account", "show", "--only-show-errors", "-o", "json"]))
    if current["id"] != SUBSCRIPTION or current["tenantId"] != TENANT:
        raise MigrationValidationError("wrong active subscription or tenant for directory operations")
    account = az("account", "show")
    if account["tenantId"] != TENANT or account["user"]["name"] != "valenciajuliann@hotmail.com":
        raise MigrationValidationError("wrong authorized operator or tenant")


def existing(*arguments: str) -> Any:
    try:
        return az(*arguments)
    except CloudOperationError as error:
        if str(error).endswith(": ResourceNotFound"):
            return None
        raise


def fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def backup_source(*, references_only: bool = False) -> dict[str, Any]:
    script = r"""set -eu
umask 077
systemctl is-active --quiet la70-data-pipeline && exit 1
mkdir -p /opt/la70-data/migration
python3 - <<'REMOTE_PY'
import hashlib,json,subprocess
from pathlib import Path
root=Path('/opt/la70-data/migration')
def sql(statement):
    command=['docker','exec','la70-data-postgres-1','psql','-X','-q','-U','postgres','-d','bank_agent','-Atc',statement]
    return subprocess.check_output(command).decode().strip()
metadata={'references':{}}
for table in ('customers','products','transactions','historical_complaints','credit_profiles'):
    query="SELECT json_build_object('count',count(*),'md5',md5(string_agg(row_to_json(t)::text,'' "
    query+="ORDER BY row_to_json(t)::text))) FROM app."+table+" t"
    value=sql(query)
    metadata['references'][table]=json.loads(value)
metadata['schema']=sql('SELECT version_num FROM app.alembic_version')
if metadata['schema']!='0014': raise SystemExit('Unexpected source schema')
backup=root/'database.dump'
with backup.open('wb') as target:
    subprocess.run(['docker','exec','la70-data-postgres-1','pg_dump','-U','postgres','-d','bank_agent','-Fc'],stdout=target,check=True)
backup.chmod(0o600)
digest=hashlib.sha256(backup.read_bytes()).hexdigest()
metadata.update(backup_sha256=digest,backup_blob='migration/'+digest+'/database.dump')
subprocess.run(['python3','/opt/la70-data/blob.py','upload','stla70238253ae46a02964',metadata['backup_blob'],str(backup)],check=True)
sql('CHECKPOINT')
(root/'source.json').write_text(json.dumps(metadata)+'\n')
print(json.dumps(metadata))
REMOTE_PY
"""
    if references_only:
        # Read the same schema/reference fingerprints without creating another backup or Blob object.
        script = script.split("backup=root/'database.dump'", 1)[0] + "print(json.dumps(metadata))\nREMOTE_PY\n"
    result = az(
        "vm",
        "run-command",
        "invoke",
        "-g",
        SOURCE_GROUP,
        "-n",
        SOURCE_VM,
        "--command-id",
        "RunShellScript",
        "--scripts",
        script,
    )
    messages = "\n".join(item["message"] for item in result["value"])
    records = [json.loads(line) for line in messages.splitlines() if line.startswith('{"references":')]
    if len(records) != 1:
        raise RuntimeError("source backup was not verified")
    return dict(records[0])


def copy_artifacts() -> list[dict[str, Any]]:
    source = az(
        "storage",
        "blob",
        "list",
        "--account-name",
        SOURCE_STORAGE,
        "--container-name",
        "artifacts",
        "--auth-mode",
        "login",
        "--num-results",
        "*",
    )
    transfer = STATE / "migration-transfer"
    transfer.mkdir(mode=0o700, exist_ok=True)
    copied = []
    for index, item in enumerate(source, 1):
        name = item["name"]
        origin, returned = transfer / "source.bin", transfer / "returned.bin"
        az(
            "storage",
            "blob",
            "download",
            "--account-name",
            SOURCE_STORAGE,
            "--container-name",
            "artifacts",
            "--name",
            name,
            "--file",
            str(origin),
            "--auth-mode",
            "login",
            "--overwrite",
            "true",
        )
        origin.chmod(0o600)
        digest = fingerprint(origin)
        exists = az(
            "storage",
            "blob",
            "exists",
            "--account-name",
            STORAGE,
            "--container-name",
            "artifacts",
            "--name",
            name,
            "--auth-mode",
            "login",
        )["exists"]
        if not exists:
            az(
                "storage",
                "blob",
                "upload",
                "--account-name",
                STORAGE,
                "--container-name",
                "artifacts",
                "--name",
                name,
                "--file",
                str(origin),
                "--auth-mode",
                "login",
                "--overwrite",
                "false",
            )
        az(
            "storage",
            "blob",
            "download",
            "--account-name",
            STORAGE,
            "--container-name",
            "artifacts",
            "--name",
            name,
            "--file",
            str(returned),
            "--auth-mode",
            "login",
            "--overwrite",
            "true",
        )
        returned.chmod(0o600)
        if digest != fingerprint(returned):
            raise MigrationValidationError("destination artifact SHA-256 mismatch")
        metadata = az(
            "storage",
            "blob",
            "show",
            "--account-name",
            SOURCE_STORAGE,
            "--container-name",
            "artifacts",
            "--name",
            name,
            "--auth-mode",
            "login",
        )
        # Azure's list API omits HTTP quotes; the show API includes them.
        if metadata["properties"]["etag"].strip('"') != item["properties"]["etag"].strip('"'):
            raise MigrationValidationError("source artifact changed during migration")
        copied.append({"name": name, "sha256": digest, "bytes": origin.stat().st_size})
        origin.unlink()
        returned.unlink()
        print(f"Artifacts verified: {index}/{len(source)}", flush=True)
    return copied


def prepare() -> None:
    guard()
    STATE.mkdir(parents=True, exist_ok=True)
    STATE.chmod(0o700)
    source = az("vm", "show", "-g", SOURCE_GROUP, "-n", SOURCE_VM)
    if source["location"] != "westus2" or source["hardwareProfile"]["vmSize"] != "Standard_B2as_v2":
        raise MigrationValidationError("unexpected source VM scope")
    expected = (
        f"/subscriptions/{SUBSCRIPTION}/resourceGroups/{SOURCE_GROUP}"
        f"/providers/Microsoft.Compute/virtualMachines/{SOURCE_VM}"
    )
    if source["id"].lower() != expected.lower():
        raise MigrationValidationError("unexpected source resource")
    az(
        "group",
        "create",
        "-n",
        GROUP,
        "-l",
        "westus2",
        "--tags",
        "project=la70",
        "component=data-engineering",
        "env=test",
    )
    print("Deploying private engineering storage.", flush=True)
    operator = az("ad", "signed-in-user", "show")["id"]
    az(
        "deployment",
        "group",
        "create",
        "-g",
        GROUP,
        "-n",
        "data-engineering-storage",
        "--template-file",
        str(PACKAGE / "storage.json"),
        "--parameters",
        f"storageName={STORAGE}",
        f"operatorId={operator}",
    )
    print("Deploying closed engineering networking.", flush=True)
    key = (STATE / "ssh.pub").read_text().strip()
    az(
        "deployment",
        "group",
        "create",
        "-g",
        GROUP,
        "-n",
        "data-engineering-network",
        "--template-file",
        str(PACKAGE / "database.json"),
        "--parameters",
        f"sshPublicKey={key}",
        "deployVm=false",
    )
    print("Canonical storage and closed network prepared; source VM remains running.", flush=True)
    print("Creating and publishing the source database backup.", flush=True)
    backup = backup_source()
    source_disk = source["storageProfile"]["osDisk"]["managedDisk"]["id"]
    az("vm", "update", "-g", SOURCE_GROUP, "-n", SOURCE_VM, "--set", "storageProfile.osDisk.deleteOption=Detach")
    print("Creating the checkpointed disk snapshot.", flush=True)
    snapshot = existing("snapshot", "show", "-g", GROUP, "-n", SNAPSHOT)
    if snapshot is None:
        snapshot = az(
            "snapshot",
            "create",
            "-g",
            GROUP,
            "-n",
            SNAPSHOT,
            "-l",
            "westus2",
            "--source",
            source_disk,
            "--incremental",
            "true",
            "--sku",
            "Standard_LRS",
        )
    if snapshot["creationData"]["sourceResourceId"].lower() != source_disk.lower():
        raise MigrationValidationError("snapshot points to a different source disk")
    print("Preparing the engineering disk clone.", flush=True)
    disk = existing("disk", "show", "-g", GROUP, "-n", DISK)
    if disk is None:
        disk = az(
            "disk",
            "create",
            "-g",
            GROUP,
            "-n",
            DISK,
            "-l",
            "westus2",
            "--source",
            snapshot["id"],
            "--sku",
            "StandardSSD_LRS",
        )
    if disk["creationData"]["sourceResourceId"].lower() != snapshot["id"].lower():
        raise MigrationValidationError("engineering disk points to a different snapshot")
    if snapshot["provisioningState"] != "Succeeded" or disk["provisioningState"] != "Succeeded":
        raise MigrationValidationError("disk protection incomplete")
    artifacts = copy_artifacts()
    metadata = {
        "source_vm": source["id"],
        "source_disk": source_disk,
        "source_principal": source["identity"]["principalId"],
        "snapshot": snapshot["id"],
        "disk": disk["id"],
        "backup": backup,
        "artifacts": artifacts,
        "destination_group": GROUP,
        "destination_vm": VM,
        "destination_storage": STORAGE,
        "status": "prepared; source VM preserved; replacement requires explicit approval",
    }
    (STATE / "migration.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (STATE / "migration.json").chmod(0o600)
    (STATE / "os-disk-id").write_text(disk["id"] + "\n")
    print(
        json.dumps(
            {"status": metadata["status"], "artifacts_verified": len(artifacts), "snapshot": SNAPSHOT, "disk": DISK}
        )
    )


def cutover(confirmed: bool) -> None:
    if not confirmed:
        raise MigrationValidationError("explicit approval is required to replace the source VM")
    guard()
    manifest = STATE / "migration.json"
    metadata = json.loads(manifest.read_text())
    proof = json.loads((STATE / "restore-verification.json").read_text())
    if proof.get("verified") is not True or proof.get("manifest_sha256") != fingerprint(manifest):
        raise MigrationValidationError("a successful restore of this exact manifest is required")
    expected_vm = (
        f"/subscriptions/{SUBSCRIPTION}/resourceGroups/{SOURCE_GROUP}"
        f"/providers/Microsoft.Compute/virtualMachines/{SOURCE_VM}"
    )
    if metadata["source_vm"].lower() != expected_vm.lower():
        raise MigrationValidationError("source VM is outside the approved scope")
    source = az("vm", "show", "-g", SOURCE_GROUP, "-n", SOURCE_VM)
    source_disk = source["storageProfile"]["osDisk"]
    if source_disk["deleteOption"] != "Detach":
        raise MigrationValidationError("the original OS disk must be retained")
    if source_disk["managedDisk"]["id"].lower() != metadata["source_disk"].lower():
        raise MigrationValidationError("the protected source disk changed")
    # The backup path is a fixed private Blob key; role credentials never enter arguments.
    current = backup_source(references_only=True)
    if current["schema"] != metadata["backup"]["schema"] or current["references"] != metadata["backup"]["references"]:
        raise MigrationValidationError("source reference data changed since the verified preparation")
    disk = az("disk", "show", "-g", GROUP, "-n", DISK)
    if disk.get("managedBy") or disk["id"].lower() != metadata["disk"].lower():
        raise MigrationValidationError("prepared disk is attached or outside the approved scope")
    print("Approved cutover: stopping only the source data VM.", flush=True)
    az("vm", "deallocate", "-g", SOURCE_GROUP, "-n", SOURCE_VM)
    final_name = "snap-data-engineering-final-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    snapshot = az(
        "snapshot",
        "create",
        "-g",
        GROUP,
        "-n",
        final_name,
        "-l",
        "westus2",
        "--source",
        metadata["source_disk"],
        "--incremental",
        "true",
        "--sku",
        "Standard_LRS",
    )
    if snapshot["provisioningState"] != "Succeeded":
        raise MigrationValidationError("stopped-source snapshot did not succeed; original VM retained")
    # Replace only the unattached prepared clone. Original disk and both snapshots remain protected.
    az("disk", "delete", "-g", GROUP, "-n", DISK, "--yes")
    disk = az(
        "disk",
        "create",
        "-g",
        GROUP,
        "-n",
        DISK,
        "-l",
        "westus2",
        "--source",
        snapshot["id"],
        "--sku",
        "StandardSSD_LRS",
    )
    if disk["provisioningState"] != "Succeeded":
        raise MigrationValidationError("final disk clone did not succeed; original VM retained")
    metadata.update(final_snapshot=snapshot["id"], disk=disk["id"], status="protected; approved replacement started")
    manifest.write_text(json.dumps(metadata, indent=2) + "\n")
    (STATE / "os-disk-id").write_text(disk["id"] + "\n")
    print("Stopped-source snapshot and final clone verified; original OS disk retained.", flush=True)
    az("vm", "delete", "-g", SOURCE_GROUP, "-n", SOURCE_VM, "--yes")
    print("Source VM resource replaced; deploying the engineering VM from its protected disk.", flush=True)
    key = (STATE / "ssh.pub").read_text().strip()
    az(
        "deployment",
        "group",
        "create",
        "-g",
        GROUP,
        "-n",
        "data-engineering-compute",
        "--template-file",
        str(PACKAGE / "database.json"),
        "--parameters",
        f"sshPublicKey={key}",
        f"osDiskId={disk['id']}",
    )
    destination = az("vm", "show", "-g", GROUP, "-n", VM)
    scope = (
        f"/subscriptions/{SUBSCRIPTION}/resourceGroups/{GROUP}/providers/Microsoft.Storage"
        f"/storageAccounts/{STORAGE}/blobServices/default/containers/artifacts"
    )
    az(
        "role",
        "assignment",
        "create",
        "--assignee-object-id",
        destination["identity"]["principalId"],
        "--assignee-principal-type",
        "ServicePrincipal",
        "--role",
        "Storage Blob Data Contributor",
        "--scope",
        scope,
    )
    metadata.update(destination_principal=destination["identity"]["principalId"], status="booted; validation pending")
    manifest.write_text(json.dumps(metadata, indent=2) + "\n")
    print("Engineering VM created. Source disk, snapshots, storage, and networking retained for recovery.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "cutover"))
    parser.add_argument("--confirm-replace-source", action="store_true")
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            prepare()
        else:
            cutover(args.confirm_replace_source)
    except MigrationValidationError as error:
        print(f"Migration validation failed: {error}.", file=sys.stderr)
        raise SystemExit(1) from None
    except CloudOperationError as error:
        print(f"Migration failed: {error}. No credentials printed.", file=sys.stderr)
        raise SystemExit(1) from None
    except Exception as error:
        print(f"Migration failed ({type(error).__name__}); no credentials printed.", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
