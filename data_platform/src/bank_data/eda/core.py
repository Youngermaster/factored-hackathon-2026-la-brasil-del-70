"""Run identity, contracts, atomic artifacts and bounded local database access."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PHASES = ("inventory", "profile", "curate", "analyze", "report")
CONTRACTS = json.loads(Path(__file__).with_name("contracts.json").read_text())
FK = {
    "customers": {"registration_branch_id": ("branches", "branch_id")},
    "products": {"customer_id": ("customers", "customer_id"), "opening_branch_id": ("branches", "branch_id")},
    "service_agents": {"assigned_branch_id": ("branches", "branch_id")},
    "transactions": {
        "customer_id": ("customers", "customer_id"),
        "product_id": ("products", "product_id"),
        "branch_id": ("branches", "branch_id"),
    },
    "call_center_interactions": {
        "customer_id": ("customers", "customer_id"),
        "agent_id": ("service_agents", "agent_id"),
    },
    "call_transcripts": {
        "interaction_id": ("call_center_interactions", "interaction_id"),
        "customer_id": ("customers", "customer_id"),
        "agent_id": ("service_agents", "agent_id"),
    },
    "satisfaction_surveys": {
        "interaction_id": ("call_center_interactions", "interaction_id"),
        "customer_id": ("customers", "customer_id"),
        "agent_id": ("service_agents", "agent_id"),
    },
    "digital_events": {"customer_id": ("customers", "customer_id"), "product_id": ("products", "product_id")},
    "complaints": {
        "customer_id": ("customers", "customer_id"),
        "affected_product_id": ("products", "product_id"),
        "related_branch_id": ("branches", "branch_id"),
        "origin_interaction_id": ("call_center_interactions", "interaction_id"),
        "assigned_agent_id": ("service_agents", "agent_id"),
    },
    "campaign_sends": {
        "campaign_id": ("marketing_campaigns", "campaign_id"),
        "customer_id": ("customers", "customer_id"),
    },
}
# Only low-cardinality business dimensions can leave the local warehouse.
CATEGORIES = {
    "country",
    "segment",
    "customer_status",
    "product_type",
    "currency",
    "product_status",
    "branch_type",
    "branch_status",
    "geographic_zone",
    "agent_type",
    "experience_level",
    "agent_status",
    "work_shift",
    "campaign_type",
    "campaign_objective",
    "campaign_status",
    "target_country",
    "target_segment",
    "transaction_type",
    "transaction_category",
    "transaction_status",
    "channel",
    "transaction_country",
    "interaction_type",
    "contact_reason",
    "reason_category",
    "was_resolved",
    "was_escalated",
    "requires_followup",
    "detected_sentiment",
    "has_transcript",
    "has_recording",
    "detected_language",
    "audio_quality",
    "survey_type",
    "nps_category",
    "event_type",
    "event_category",
    "platform",
    "case_type",
    "category",
    "subcategory",
    "reception_channel",
    "priority",
    "status",
    "sla_breached",
    "send_channel",
    "send_status",
    "was_delivered",
    "was_opened",
    "was_clicked",
    "had_conversion",
    "source_currency",
    "target_currency",
}
POST_OUTCOME = [
    "status",
    "resolution_date",
    "closing_date",
    "sla_breached",
    "resolution_days",
    "resolution",
    "compensation_granted",
    "resolution_satisfaction",
    "was_resolved",
    "was_escalated",
    "requires_followup",
    "agent_text",
    "full_text",
    "detected_intents",
]


def qi(name: str) -> str:
    """Quote trusted contract names; reject accidental SQL fragments."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError("Invalid SQL identifier")
    return f'"{name}"'


def literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)


def now() -> str:
    return datetime.now(UTC).isoformat()


def writer_is_active(lock: Path) -> bool:
    """Return true only when a lock belongs to a currently live process."""
    try:
        pid = int(read_json(lock)["pid"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        # Legacy timestamp-only locks cannot prove their owner is gone.
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def code_identity() -> dict[str, str]:
    pipeline_modules = ("core.py", "inventory.py", "profile.py", "curate.py", "analyze.py", "report.py")
    files = [Path(__file__).with_name(name) for name in pipeline_modules]
    files.append(Path(__file__).with_name("contracts.json"))
    root = Path(__file__).resolve().parents[4]
    lockfile = root / "uv.lock"
    if lockfile.exists():
        files.append(lockfile)
    fingerprint = hashlib.sha256("".join(p.name + digest(p) for p in files).encode()).hexdigest()
    git = shutil.which("git")
    if git is None:
        return {"git_sha": "unavailable", "code_sha256": fingerprint}
    result = subprocess.run(  # noqa: S603 - resolved git executable and fixed read-only arguments
        [git, "rev-parse", "HEAD"], capture_output=True, text=True, check=False, cwd=root
    )
    return {"git_sha": result.stdout.strip() or "unavailable", "code_sha256": fingerprint}


@contextmanager
def phase(run: Path, name: str) -> Any:
    """One writer per run; only successful artifacts are visible to the UI."""
    lock = run / ".writer.lock"
    try:
        handle = lock.open("x")
    except FileExistsError:
        raise RuntimeError("Run is locked; check for an active writer before removing .writer.lock") from None
    try:
        with handle:
            json.dump({"pid": os.getpid(), "started_at": now()}, handle)
        status = read_json(run / "status.json") if (run / "status.json").exists() else {}
        for downstream in PHASES[PHASES.index(name) :]:
            status[downstream] = {"state": "pending"}
        status[name] = {"state": "running", "started_at": now()}
        write_json(run / "status.json", status)
        try:
            yield
        except BaseException as error:
            # SQL exceptions may include cell contents. Persist only their type.
            status[name].update(state="failed", error_type=type(error).__name__, finished_at=now())
            write_json(run / "status.json", status)
            raise
        else:
            status[name].update(state="complete", finished_at=now())
            write_json(run / "status.json", status)
    finally:
        lock.unlink(missing_ok=True)


def require(run: Path, predecessor: str) -> None:
    if read_json(run / "status.json").get(predecessor, {}).get("state") != "complete":
        raise RuntimeError(f"Complete {predecessor} first")
    if read_json(run / "manifest.json")["code"]["code_sha256"] != code_identity()["code_sha256"]:
        raise RuntimeError("Analysis code changed; create a new inventory")


def connect(run: Path) -> Any:
    import duckdb

    connection = duckdb.connect(str(run / "warehouse.duckdb"))
    connection.execute("SET memory_limit='2GB'")
    connection.execute("SET threads=2")
    connection.execute("SET preserve_insertion_order=true")
    connection.execute(f"SET temp_directory={literal(str(run / 'tmp'))}")
    connection.execute("SET enable_progress_bar=false")
    return connection


def records(connection: Any, sql: str) -> list[dict[str, Any]]:
    cursor = connection.execute(sql)
    columns = [entry[0] for entry in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def fields(table: str) -> list[dict[str, Any]]:
    return list(CONTRACTS[table]["columns"])


def keys(table: str) -> list[str]:
    return [column["name"] for column in fields(table) if column["pk"]]


def present(expression: str) -> str:
    return f"NULLIF(trim({expression}), '') IS NOT NULL"
