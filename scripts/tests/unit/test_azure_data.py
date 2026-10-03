"""Safety, artifact integrity, and stage ordering for the Azure data deployment."""

import hashlib
import importlib.util
import io
import json
import subprocess
import tarfile
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[3]


def load_module(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"azure_data_{name}", ROOT / "deploy" / "azure-data" / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_artifact_download_checks_hash_before_replacing_existing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blob = load_module("blob")
    monkeypatch.setattr(blob, "_token", lambda: "private-token-value")
    monkeypatch.setattr(blob.urllib.request, "urlopen", lambda *_args, **_kwargs: io.BytesIO(b"new-data"))
    path = tmp_path / "release.tar.gz"
    path.write_bytes(b"previous-good-release")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        blob.transfer("download", "stla70test", "releases/archive", path, "0" * 64)
    assert path.read_bytes() == b"previous-good-release"
    assert not (tmp_path / "release.tar.gz.partial").exists()
    blob.transfer("download", "stla70test", "releases/archive", path, hashlib.sha256(b"new-data").hexdigest())
    assert path.read_bytes() == b"new-data"


def test_artifact_address_rejects_untrusted_hosts_before_request(monkeypatch: pytest.MonkeyPatch) -> None:
    blob = load_module("blob")
    monkeypatch.setattr(blob, "_token", lambda: pytest.fail("invalid address reached authentication"))
    with pytest.raises(ValueError, match="invalid artifact address"):
        blob.transfer("download", "attacker.example", "archive", Path("unused"), "0" * 64)


def test_execution_evidence_contains_hashes_and_declared_snapshot(tmp_path: Path) -> None:
    runtime = load_module("runtime")
    run = tmp_path / "run"
    gold = tmp_path / "warehouse" / "gold"
    run.mkdir()
    gold.mkdir(parents=True)
    (run / "validation.log").write_text("passed\n")
    (run / "reconciliation.log").write_text("customers: 74\nproducts: 150\n")
    (run / "ingest.log").write_text("loaded=0 unchanged=13\n")
    (gold / "customers_serving.parquet").write_bytes(b"artifact-fixture")
    runtime.write_evidence(run, gold.parent, "a" * 40, "sample", "succeeded")
    evidence = json.loads((run / "result.json").read_text())
    assert evidence["code_revision"] == "a" * 40
    assert evidence["snapshot_date"] == "2026-06-17"
    assert evidence["gold"]["customers_serving.parquet"] == hashlib.sha256(b"artifact-fixture").hexdigest()
    assert "result.json" not in evidence["artifacts"]
    assert evidence["reconciliation_counts"] == {"customers": 74, "products": 150}
    assert evidence["ingestion"] == {"loaded": 0, "unchanged": 13}


def test_infrastructure_closes_ingress_and_disables_storage_keys() -> None:
    resources = json.loads((ROOT / "deploy" / "azure-data" / "main.json").read_text())["resources"]
    storage = next(item for item in resources if item["type"] == "Microsoft.Storage/storageAccounts")
    assert storage["properties"]["allowSharedKeyAccess"] is False
    assert storage["properties"]["allowBlobPublicAccess"] is False
    nsg = next(item for item in resources if item["type"] == "Microsoft.Network/networkSecurityGroups")
    assert all(rule["properties"]["access"] == "Deny" for rule in nsg["properties"]["securityRules"])
    vm = next(item for item in resources if item["type"] == "Microsoft.Compute/virtualMachines")
    assert vm["identity"]["type"] == "SystemAssigned"
    assert vm["properties"]["osProfile"]["linuxConfiguration"]["disablePasswordAuthentication"] is True


@pytest.mark.parametrize("failure", ["build", "test", "source"])
def test_failed_validation_never_reaches_postgres_or_seed(tmp_path: Path, failure: str) -> None:
    root = tmp_path / "runtime"
    release = root / "releases" / ("a" * 40)
    release.mkdir(parents=True)
    (root / "owner.env").write_text("APP_ENV=test\n")
    tools = tmp_path / "bin"
    tools.mkdir()
    trace = tmp_path / "trace"
    uv = tools / "uv"
    failed_command = "python deploy/azure-data/source.py restore" if failure == "source" else f"bank-data {failure}"
    uv.write_text(
        f'#!/bin/sh\nprintf "%s\\n" "$*" >> "$TRACE"\ncase "$*" in *"{failed_command}"*) exit 5 ;; esac\nexit 0\n'
    )
    uv.chmod(0o700)
    docker = tools / "docker"
    docker.write_text('#!/bin/sh\nprintf "postgres-reached\\n" >> "$TRACE"\nexit 0\n')
    docker.chmod(0o700)
    # Inherit only the variables needed by this fixture, not real database credentials.
    result = subprocess.run(
        [
            "bash",
            str(ROOT / "deploy" / "azure-data" / "run.sh"),
            "a" * 40,
            "local" if failure == "source" else "sample",
            str(root),
            "b" * 64,
        ],
        env={"PATH": f"{tools}:/usr/bin:/bin", "TRACE": str(trace)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 5
    assert "postgres-reached" not in trace.read_text()
    assert "bank-data seed" not in trace.read_text()
    (run,) = (root / "runs").iterdir()
    assert (run / "status").read_text().strip() == "failed"
    if failure == "source":
        assert "bank-data ingest" not in trace.read_text()


def test_source_archive_excludes_ancillary_files_and_restores_idempotently(tmp_path: Path) -> None:
    source = load_module("source")
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "customers.csv").write_bytes(b"synthetic-customer-fixture\n")
    partition = inputs / "transactions/year=2026/month=06/day=17"
    partition.mkdir(parents=True)
    (partition / "transactions_20260617.csv").write_bytes(b"synthetic-transaction-fixture\n")
    (inputs / ".env").write_text("private-fixture-must-not-enter-archive")
    (inputs / "dictionary.pdf").write_bytes(b"private-ancillary-fixture")
    ancillary = inputs / "warehouse-local"
    ancillary.mkdir()
    (ancillary / "customers.csv").write_bytes(b"generated-not-source")
    archive = tmp_path / "archive.tar.gz"
    receipt = source.pack(inputs, archive, "a" * 40)
    assert receipt["objects"] == 2
    with tarfile.open(archive) as bundle:
        assert set(bundle.getnames()) == {
            source.MANIFEST,
            "customers.csv",
            "transactions/year=2026/month=06/day=17/transactions_20260617.csv",
        }
    target = tmp_path / "restored"
    assert source.restore(archive, target, receipt["sha256"]) == receipt
    assert source.restore(archive, target, receipt["sha256"]) == receipt
    assert (target / "customers.csv").read_bytes() == (inputs / "customers.csv").read_bytes()
    # A local write must survive a rerun; it causes a failure rather than a silent replacement.
    (target / "customers.csv").write_bytes(b"existing-state")
    with pytest.raises(ValueError, match="existing source differs"):
        source.restore(archive, target, receipt["sha256"])
    assert (target / "customers.csv").read_bytes() == b"existing-state"


def test_source_pack_rejects_symlinks_without_publishing(tmp_path: Path) -> None:
    source = load_module("source")
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    outside = tmp_path / "private.txt"
    outside.write_bytes(b"private-fixture")
    (inputs / "customers.csv").symlink_to(outside)
    archive = tmp_path / "archive.tar.gz"
    with pytest.raises(ValueError, match="link"):
        source.pack(inputs, archive, "a" * 40)
    assert not archive.exists()


@pytest.mark.parametrize("fault", ["hash", "traversal", "symlink", "missing", "extra", "duplicate", "size"])
def test_source_restore_rejects_invalid_members_without_changing_destination(tmp_path: Path, fault: str) -> None:
    source = load_module("source")
    data = b"synthetic-source-fixture"
    name = "../customers.csv" if fault == "traversal" else "customers.csv"
    document = {
        "dataset_version": "organizer-v1.0.0-2026-08-31",
        "snapshot_date": "2026-06-17",
        "code_revision": "a" * 40,
        "files": [{"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}],
    }
    archive = tmp_path / "archive.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        body = json.dumps(document).encode()
        info = tarfile.TarInfo(source.MANIFEST)
        info.size = len(body)
        bundle.addfile(info, io.BytesIO(body))
        if fault != "missing":
            info = tarfile.TarInfo(name)
            payload = data + b"changed" if fault == "size" else b"x" * len(data) if fault == "hash" else data
            info.size = len(payload)
            if fault == "symlink":
                info.type, info.linkname, info.size = tarfile.SYMTYPE, "../outside", 0
            bundle.addfile(info, io.BytesIO(payload))
            if fault == "duplicate":
                bundle.addfile(info, io.BytesIO(payload))
            if fault == "extra":
                info = tarfile.TarInfo(".env")
                info.size = len(data)
                bundle.addfile(info, io.BytesIO(data))
    destination = tmp_path / "source"
    destination.mkdir()
    (destination / "previous.csv").write_bytes(b"retained-state")
    with pytest.raises(ValueError, match=r"invalid|unexpected|incomplete|SHA-256"):
        source.restore(archive, destination, source.sha256(archive))
    assert [path.name for path in destination.iterdir()] == ["previous.csv"]
    assert (destination / "previous.csv").read_bytes() == b"retained-state"
    assert not (tmp_path / "customers.csv").exists()


def test_source_restore_rejects_archive_hash_before_extracting(tmp_path: Path) -> None:
    source = load_module("source")
    archive = tmp_path / "archive.tar.gz"
    archive.write_bytes(b"unverified-fixture")
    with pytest.raises(ValueError, match="archive SHA-256 mismatch"):
        source.restore(archive, tmp_path / "source", "0" * 64)
    assert not (tmp_path / "source").exists()
