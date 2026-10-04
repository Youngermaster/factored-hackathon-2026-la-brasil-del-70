"""Runtime evidence and a seed guard for the bounded Azure data deployment."""

import argparse
import asyncio
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

from bank_agent.adapters.persistence.postgres.database import DatabaseRole, create_engine, open_transaction
from bank_agent.bootstrap.persistence import owner_database_url
from bank_agent.bootstrap.settings import load_settings
from bank_data.config import load_config
from bank_data.settings import DEFAULT_CONFIG_FILE


async def database_empty() -> bool:
    settings = load_settings(owner=True)
    engine = create_engine(owner_database_url(settings.database), pooled=False)
    try:
        async with open_transaction(engine, DatabaseRole.SEED) as connection:
            return int((await connection.execute(text("SELECT count(*) FROM app.customers"))).scalar_one()) == 0
    finally:
        await engine.dispose()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def write_evidence(run: Path, warehouse: Path, revision: str, source: str, status: str) -> None:
    config = load_config(DEFAULT_CONFIG_FILE)
    artifacts = [path for path in run.rglob("*") if path.is_file() and path.name != "result.json"]
    gold = sorted((warehouse / "gold").glob("*_serving.parquet"))
    payload = {
        "schema_version": "1.0.0",
        "recorded_at": datetime.now(UTC).isoformat(),
        "code_revision": revision,
        "source": source,
        "status": status,
        "dataset_version": config.dataset.version,
        "snapshot_date": config.dataset.snapshot_date.isoformat(),
        "llm_provider": "fake",
        "gold": {path.name: file_hash(path) for path in gold},
        "artifacts": {path.relative_to(run).as_posix(): file_hash(path) for path in artifacts},
    }
    reconciliation = run / "reconciliation.log"
    if reconciliation.is_file():
        payload["reconciliation_counts"] = {
            table: int(count)
            for table, count in re.findall(r"^([a-z_]+): ([0-9]+)$", reconciliation.read_text(), re.MULTILINE)
        }
    ingestion = run / "ingest.log"
    if ingestion.is_file():
        payload["ingestion"] = {
            name: int(count) for name, count in re.findall(r"\b([a-z_]+)=([0-9]+)\b", ingestion.read_text())
        }
    application = run / "application.json"
    if application.is_file():
        payload["application_checks"] = json.loads(application.read_text())
    (run / "result.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("empty")
    evidence = sub.add_parser("evidence")
    evidence.add_argument("run", type=Path)
    evidence.add_argument("warehouse", type=Path)
    evidence.add_argument("revision")
    evidence.add_argument("source")
    evidence.add_argument("status", choices=("succeeded", "failed"))
    args = parser.parse_args()
    if args.command == "empty":
        return 0 if asyncio.run(database_empty()) else 10
    write_evidence(args.run, args.warehouse, args.revision, args.source, args.status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
