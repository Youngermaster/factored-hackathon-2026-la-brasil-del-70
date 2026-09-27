"""Freeze and validate a local input manifest without assuming remote completeness."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from bank_data.eda.core import CONTRACTS, code_identity, digest, now, phase, read_json, write_json, writer_is_active


def inventory(source: Path, output: Path) -> Path:
    source, output = source.resolve(), output.resolve()
    if not source.is_dir() or source == output or source.is_relative_to(output):
        raise ValueError("Source must be an existing directory distinct from the output tree")
    entries: list[dict[str, Any]] = []
    ignored: Counter[str] = Counter()
    for path in sorted(source.rglob("*")):
        if path.is_relative_to(output) or not path.is_file():
            continue
        relative = path.relative_to(source)
        table = path.stem if len(relative.parts) == 1 else relative.parts[0]
        if path.suffix != ".csv" or table not in CONTRACTS or path.is_symlink():
            ignored["unknown_table_or_non_csv"] += 1
            continue
        before = path.stat()
        sha = digest(path)
        with path.open(encoding="utf-8-sig", newline="") as stream:
            header = next(csv.reader(stream), [])
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError("Input changed during inventory; retry after the download finishes")
        partition = {part.split("=", 1)[0]: part.split("=", 1)[1] for part in relative.parts if "=" in part}
        partition_date = None
        if {"year", "month", "day"} <= partition.keys():
            partition_date = date(*(int(partition[k]) for k in ("year", "month", "day"))).isoformat()
        entries.append(
            {
                "path": str(relative),
                "table": table,
                "bytes": after.st_size,
                "mtime_ns": after.st_mtime_ns,
                "sha256": sha,
                "columns": header,
                "partition_date": partition_date,
            }
        )
    if not entries:
        raise ValueError("No recognized CSV tables found")
    code = code_identity()
    identity = {
        "files": [{k: v for k, v in entry.items() if k != "mtime_ns"} for entry in entries],
        "code": code,
        "settings": {"threads": 2, "memory_limit": "2GB", "scope": "full_local", "sample_seed": 70},
    }
    run_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:20]
    run = output / run_id
    run.mkdir(parents=True, exist_ok=True)
    if (run / "manifest.json").exists() and (run / "status.json").exists():
        lock = run / ".writer.lock"
        if lock.exists():
            if writer_is_active(lock):
                raise RuntimeError("Run has an active writer; wait before refreshing the inventory")
            lock.unlink()
        # Refresh root/mtime for an identical copy, without invalidating analytical results.
        manifest = read_json(run / "manifest.json")
        manifest.update(source=str(source), files=entries)
        write_json(run / "manifest.json", manifest)
        return run
    with phase(run, "inventory"):
        write_json(
            run / "manifest.json",
            {
                **identity,
                "files": entries,
                "source": str(source),
                "run_id": run_id,
                "created_at": now(),
                "ignored": dict(ignored),
                "remote_completeness": "not_verified",
            },
        )
        summaries = []
        for table in CONTRACTS:
            subset = [entry for entry in entries if entry["table"] == table]
            expected = [column["name"] for column in CONTRACTS[table]["columns"]]
            dates = sorted({entry["partition_date"] for entry in subset if entry["partition_date"]})
            span = (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days + 1 if dates else 0
            summaries.append(
                {
                    "table": table,
                    "files": len(subset),
                    "bytes": sum(e["bytes"] for e in subset),
                    "schema_variants": len({tuple(e["columns"]) for e in subset}),
                    "schema_mismatch_files": sum(e["columns"] != expected for e in subset),
                    "first_partition": dates[0] if dates else None,
                    "last_partition": dates[-1] if dates else None,
                    "internal_missing_days": span - len(dates),
                    "identical_file_copies": len(subset) - len({e["sha256"] for e in subset}),
                }
            )
        write_json(run / "inventory.json", summaries)
    return run


def verify_inputs(run: Path, *, hash_content: bool = True) -> dict[str, Any]:
    manifest: dict[str, Any] = read_json(run / "manifest.json")
    source = Path(manifest["source"])
    for entry in manifest["files"]:
        path = source / entry["path"]
        stat = path.stat()
        if stat.st_size != entry["bytes"] or stat.st_mtime_ns != entry["mtime_ns"]:
            raise RuntimeError("Input changed since inventory; create a new inventory")
        if hash_content and digest(path) != entry["sha256"]:
            raise RuntimeError("Input fingerprint mismatch; create a new inventory")
    return manifest
