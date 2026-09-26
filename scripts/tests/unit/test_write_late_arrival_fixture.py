import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "write_late_arrival_fixture.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("write_late_arrival_fixture", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["write_late_arrival_fixture"] = module
    spec.loader.exec_module(module)
    return module


fixture = _load()


def test_committed_fixture_matches_the_script() -> None:
    assert fixture.main(["write_late_arrival_fixture.py", "--check"]) == 0


def test_fixture_is_labeled_and_uses_only_invented_identifiers() -> None:
    assert "synthetic test data made by the team" in (fixture.ROOT / "FIXTURE.md").read_text(encoding="utf-8")
    for content in fixture.files().values():
        assert content.startswith("\ufeff")
        for line in content.splitlines()[1:]:
            identifiers = [field for field in line.split(",") if field[:4] in {"CLI-", "PRD-", "TRX-", "AGT-"}]
            assert all("FIX" in identifier for identifier in identifiers)


def test_check_reports_a_modified_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fixture, "ROOT", tmp_path)
    assert fixture.main(["write_late_arrival_fixture.py"]) == 0
    assert fixture.main(["write_late_arrival_fixture.py", "--check"]) == 0
    (tmp_path / "base" / "customers.csv").write_text("changed", encoding="utf-8")
    assert fixture.main(["write_late_arrival_fixture.py", "--check"]) == 1
