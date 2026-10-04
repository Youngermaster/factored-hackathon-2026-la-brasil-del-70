"""The ADR status guard keeps records and their index aligned."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).resolve().parents[2] / "checks" / "check_adr_statuses.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_adr_statuses", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_adr_statuses"] = module
    spec.loader.exec_module(module)
    return module


guard = _load()


def _write_fixture(root: Path, *, index_status: str = "Accepted", record_status: str = "accepted") -> None:
    root.mkdir()
    (root / "README.md").write_text(
        "| Number | Title | Status | Date |\n"
        "|---|---|---|---|\n"
        f"| [0001](0001-example.md) | Example | {index_status} | 2026-10-01 |\n",
        encoding="utf-8",
    )
    (root / "0001-example.md").write_text(
        f"# 0001: Example\n\n- Status: {record_status}\n- Date: 2026-10-01\n",
        encoding="utf-8",
    )


def test_matching_statuses_pass_case_insensitively(tmp_path: Path) -> None:
    adr_dir = tmp_path / "adr"
    _write_fixture(adr_dir)

    assert guard.check(adr_dir) == []


def test_mismatched_status_is_reported(tmp_path: Path) -> None:
    adr_dir = tmp_path / "adr"
    _write_fixture(adr_dir, index_status="Superseded")

    assert guard.check(adr_dir) == [
        f"{adr_dir / '0001-example.md'}: status 'accepted' does not match index status 'superseded'"
    ]


def test_unindexed_record_is_reported(tmp_path: Path) -> None:
    adr_dir = tmp_path / "adr"
    _write_fixture(adr_dir)
    extra = adr_dir / "0002-extra.md"
    extra.write_text("# 0002: Extra\n\n- Status: accepted\n", encoding="utf-8")

    assert guard.check(adr_dir) == [f"{extra}: ADR is missing from {adr_dir / 'README.md'}"]
