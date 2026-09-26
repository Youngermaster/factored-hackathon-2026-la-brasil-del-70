import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "checks" / "check_data_sample.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_data_sample", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_data_sample"] = module
    spec.loader.exec_module(module)
    return module


guard = _load()
SECTIONS = "\n\n".join(guard.REQUIRED_SECTIONS)


def _readme(counts: dict[str, tuple[int, int]], sections: str = SECTIONS) -> str:
    rows = "\n".join(f"| {name} | {sample} | {preview} |" for name, (sample, preview) in counts.items())
    body = sections.replace(
        "## Row counts", "## Row counts\n\n| Table | Sample rows | Preview rows |\n|---|---|---|\n" + rows
    )
    return "# Sample\n\n" + body + "\n"


def _write_csv(path: Path, rows: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\ufeffid,name\n" + "".join(f"{index},x\n" for index in range(rows)), encoding="utf-8")


def _valid_sample(root: Path) -> Path:
    _write_csv(root / "customers.csv", 3)
    _write_csv(root / "transactions" / "year=2026" / "month=06" / "day=01" / "transactions_20260601.csv", 2)
    _write_csv(root / "transactions" / "year=2026" / "month=06" / "day=02" / "transactions_20260602.csv", 1)
    _write_csv(root / "preview" / "customers.csv", 2)
    _write_csv(root / "preview" / "transactions.csv", 2)
    (root / "README.md").write_text(_readme({"customers": (3, 2), "transactions": (3, 2)}), encoding="utf-8")
    return root


def test_a_bounded_documented_sample_passes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _valid_sample(tmp_path)
    assert guard.main(["check_data_sample.py", str(root)]) == 0
    assert "within bounds" in capsys.readouterr().out


def test_fails_above_the_row_limit(tmp_path: Path) -> None:
    root = _valid_sample(tmp_path)
    _write_csv(root / "customers.csv", 4_999)
    (root / "README.md").write_text(_readme({"customers": (4_999, 2), "transactions": (3, 2)}), encoding="utf-8")
    problems = guard.check(root)
    assert any("above the limit of 5000" in problem for problem in problems)


def test_fails_when_a_table_is_missing_from_the_readme_or_miscounted(tmp_path: Path) -> None:
    root = _valid_sample(tmp_path)
    (root / "README.md").write_text(_readme({"customers": (2, 2)}), encoding="utf-8")
    problems = guard.check(root)
    assert any("'transactions' is missing from the row counts" in problem for problem in problems)
    assert any("row counts for 'customers'" in problem for problem in problems)


def test_fails_without_readme_or_required_sections(tmp_path: Path) -> None:
    root = _valid_sample(tmp_path)
    (root / "README.md").write_text(
        _readme({"customers": (3, 2), "transactions": (3, 2)}, SECTIONS.replace("## Data-use terms", "")),
        encoding="utf-8",
    )
    assert any("missing section '## Data-use terms'" in problem for problem in guard.check(root))
    (root / "README.md").unlink()
    assert any("README is missing" in problem for problem in guard.check(root))


def test_fails_on_unexpected_file_types(tmp_path: Path) -> None:
    root = _valid_sample(tmp_path)
    (root / "notes.parquet").write_bytes(b"PAR1")
    (root / "credentials.env").write_text("X=1", encoding="utf-8")
    problems = guard.check(root)
    assert sum("unexpected file type" in problem for problem in problems) == 2
    assert guard.main(["check_data_sample.py", str(root)]) == 1


def test_missing_directory_fails(tmp_path: Path) -> None:
    assert guard.check(tmp_path / "absent") == [f"{tmp_path / 'absent'}: sample directory is missing"]


def test_counts_quoted_multiline_values_as_one_row(tmp_path: Path) -> None:
    path = tmp_path / "t.csv"
    path.write_text('id,text\n1,"line one\nline two"\n2,plain\n', encoding="utf-8")
    assert guard.count_rows(path) == 2
