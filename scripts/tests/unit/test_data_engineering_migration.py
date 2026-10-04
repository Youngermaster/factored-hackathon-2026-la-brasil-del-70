"""A naming migration must preserve source artifacts and reject corrupt or concurrent copies."""

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType

import pytest


def helper() -> ModuleType:
    path = Path(__file__).resolve().parents[3] / "deploy/data-engineering/migration.py"
    spec = importlib.util.spec_from_file_location("data_engineering_migration", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wrong_tenant_is_rejected_before_migration(monkeypatch: pytest.MonkeyPatch) -> None:
    module = helper()
    monkeypatch.setattr(module, "az", lambda *_args: {"tenantId": "another-tenant"})
    monkeypatch.setattr(
        module, "run", lambda *_args: json.dumps({"id": module.SUBSCRIPTION, "tenantId": module.TENANT}).encode()
    )
    with pytest.raises(ValueError, match="wrong authorized operator"):
        module.guard()


def test_vm_replacement_requires_explicit_approval_before_cloud_access(monkeypatch: pytest.MonkeyPatch) -> None:
    module = helper()
    monkeypatch.setattr(module, "guard", lambda: pytest.fail("unapproved cutover reached Azure"))
    with pytest.raises(ValueError, match="explicit approval"):
        module.cutover(False)


def test_stale_restore_proof_prevents_any_resource_mutation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = helper()
    monkeypatch.setattr(module, "STATE", tmp_path)
    monkeypatch.setattr(module, "guard", lambda: None)
    monkeypatch.setattr(module, "az", lambda *_args: pytest.fail("unverified cutover touched a resource"))
    (tmp_path / "migration.json").write_text("{}")
    (tmp_path / "restore-verification.json").write_text('{"verified": true, "manifest_sha256": "outdated"}')
    with pytest.raises(ValueError, match="this exact manifest"):
        module.cutover(True)


def test_failed_cloud_operation_reports_only_category_and_error_code(monkeypatch: pytest.MonkeyPatch) -> None:
    module = helper()
    marker = b"private-authentication-material"
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, marker, b"(AuthorizationFailed) " + marker),
    )
    with pytest.raises(module.CloudOperationError) as failure:
        module.run(["az", "deployment", "group", "create"], marker)
    assert "AuthorizationFailed" in str(failure.value)
    assert marker.decode() not in str(failure.value)


@pytest.mark.parametrize("failure", ["none", "quoted_etag", "corruption", "concurrent_change"])
def test_artifacts_are_download_verified_without_overwriting_existing_destinations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    module = helper()
    monkeypatch.setattr(module, "STATE", tmp_path)
    content = b"governed-artifact-fixture"
    uploads = []

    def fake_az(*args: str) -> object:
        if args[:3] == ("storage", "blob", "list"):
            return [{"name": "source.tar.gz", "properties": {"etag": "original-version"}}]
        if args[:3] == ("storage", "blob", "exists"):
            return {"exists": True}
        if args[:3] == ("storage", "blob", "show"):
            etag = "changed-version" if failure == "concurrent_change" else "original-version"
            if failure == "quoted_etag":
                etag = '"' + etag + '"'
            return {"properties": {"etag": etag}}
        if args[:3] == ("storage", "blob", "upload"):
            uploads.append(args)
        if args[:3] == ("storage", "blob", "download"):
            destination = Path(args[args.index("--file") + 1])
            target = args[args.index("--account-name") + 1] == module.STORAGE
            destination.write_bytes(b"corrupt-copy" if target and failure == "corruption" else content)
        return {}

    monkeypatch.setattr(module, "az", fake_az)
    if failure in ("none", "quoted_etag"):
        result = module.copy_artifacts()
        assert result == [
            {"name": "source.tar.gz", "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
        ]
        assert not list((tmp_path / "migration-transfer").iterdir())
    else:
        with pytest.raises(ValueError, match=r"mismatch|changed during migration"):
            module.copy_artifacts()
    assert not uploads


@pytest.mark.parametrize("failed_stage", ["snapshot", "disk", "none"])
def test_replacement_preserves_original_disk_and_requires_final_protection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed_stage: str
) -> None:
    module = helper()
    monkeypatch.setattr(module, "STATE", tmp_path)
    monkeypatch.setattr(module, "guard", lambda: None)
    source_id = (
        f"/subscriptions/{module.SUBSCRIPTION}/resourceGroups/{module.SOURCE_GROUP}"
        f"/providers/Microsoft.Compute/virtualMachines/{module.SOURCE_VM}"
    )
    source_disk = "protected-original-disk"
    clone = "prepared-engineering-disk"
    reference = {"schema": "0014", "references": {"customers": {"count": 200, "md5": "fixture"}}}
    metadata = {"source_vm": source_id, "source_disk": source_disk, "disk": clone, "backup": reference}
    manifest = tmp_path / "migration.json"
    manifest.write_text(json.dumps(metadata))
    (tmp_path / "restore-verification.json").write_text(
        json.dumps({"verified": True, "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()})
    )
    (tmp_path / "ssh.pub").write_text("fixture-public-key")
    monkeypatch.setattr(module, "backup_source", lambda **_kwargs: reference)
    calls: list[tuple[str, ...]] = []

    def fake_az(*args: str) -> object:
        calls.append(args)
        if args[:2] == ("vm", "show"):
            if module.SOURCE_VM in args:
                return {"storageProfile": {"osDisk": {"deleteOption": "Detach", "managedDisk": {"id": source_disk}}}}
            return {"identity": {"principalId": "new-engineering-identity"}}
        if args[:2] == ("disk", "show"):
            return {"id": clone, "managedBy": None}
        if args[:2] == ("snapshot", "create"):
            return {
                "id": "final-snapshot",
                "provisioningState": "Failed" if failed_stage == "snapshot" else "Succeeded",
            }
        if args[:2] == ("disk", "create"):
            return {"id": clone, "provisioningState": "Failed" if failed_stage == "disk" else "Succeeded"}
        return {}

    monkeypatch.setattr(module, "az", fake_az)
    if failed_stage != "none":
        with pytest.raises(ValueError, match="original VM retained"):
            module.cutover(True)
        assert not any(call[:2] == ("vm", "delete") for call in calls)
    else:
        module.cutover(True)
        deletions = [call for call in calls if call[:2] == ("vm", "delete")]
        assert deletions == [("vm", "delete", "-g", module.SOURCE_GROUP, "-n", module.SOURCE_VM, "--yes")]
        snapshot_index = next(i for i, call in enumerate(calls) if call[:2] == ("snapshot", "create"))
        clone_index = next(i for i, call in enumerate(calls) if call[:2] == ("disk", "create"))
        deletion_index = next(i for i, call in enumerate(calls) if call[:2] == ("vm", "delete"))
        assert snapshot_index < clone_index < deletion_index
    disk_deletions = [call for call in calls if call[:2] == ("disk", "delete")]
    assert all(call == ("disk", "delete", "-g", module.GROUP, "-n", module.DISK, "--yes") for call in disk_deletions)
    assert not any(call[:2] == ("snapshot", "delete") for call in calls)
    assert not any(source_disk in call for call in disk_deletions)
