"""``FilesystemEvaluationSummaries`` reads 1.0.0 and 1.1.0 summary files, newest first, and names a broken file."""

import json
from pathlib import Path
from typing import Any

import pytest

from bank_agent.adapters.evaluation.summaries import FilesystemEvaluationSummaries
from bank_agent.domain.errors import ConfigurationError

COUNT = {"count": 1, "denominator": 2}
METRICS: dict[str, Any] = {
    "cases": 2, "safe_automated_resolution": COUNT, "containment": COUNT, "escalation_missed": COUNT,
    "escalation_unnecessary": COUNT, "unsafe_outcomes": {"count": 0, "denominator": 2},
}  # fmt: skip


def _write(directory: Path, name: str, **fields: Any) -> None:
    document: dict[str, Any] = {
        "system": "proposed", "git_sha": "abc1234", "dataset_version": "scenarios-v1",
        "workflows": [{"workflow": "credit", **METRICS}], "aggregate": METRICS, **fields,
    }  # fmt: skip
    (directory / name).write_text(json.dumps(document), encoding="utf-8")


async def test_reads_both_schema_versions_newest_first(tmp_path: Path) -> None:
    _write(tmp_path, "old.json", schema_version="1.0.0", run_id="run-1", generated_at="2026-09-01T00:00:00Z")
    _write(
        tmp_path,
        "new.json",
        run_id="run-2",
        generated_at="2026-09-02T00:00:00Z",
        measurement="simulated",
        breakdowns=[{"dimension": "language", "value": "pt", "workflow": "credit", **METRICS}],
        failure_table="evals/reports/run-2/failures.csv",
    )
    summaries = await FilesystemEvaluationSummaries(tmp_path).list()
    assert [(item.run_id, item.schema_version, item.measurement) for item in summaries] == [
        ("run-2", "1.1.0", "simulated"),
        ("run-1", "1.0.0", "offline"),
    ]
    assert summaries[0].breakdowns[0].value == "pt"


async def test_a_missing_directory_publishes_nothing(tmp_path: Path) -> None:
    assert await FilesystemEvaluationSummaries(tmp_path / "missing").list() == []


async def test_a_1_0_file_with_a_1_1_field_is_refused_by_name(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "mislabeled.json",
        schema_version="1.0.0",
        run_id="run-3",
        generated_at="2026-09-03T00:00:00Z",
        measurement="projected",
    )
    with pytest.raises(ConfigurationError, match=r"mislabeled\.json"):
        await FilesystemEvaluationSummaries(tmp_path).list()
