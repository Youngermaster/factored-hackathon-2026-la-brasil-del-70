import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "checks" / "check_coverage_gates.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_coverage_gates", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_coverage_gates"] = module
    spec.loader.exec_module(module)
    return module


gates = _load()


def _write_inputs(tmp_path: Path, table: str, files: dict[str, tuple[int, int]]) -> list[str]:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(table, encoding="utf-8")
    report = {
        "files": {
            path: {"summary": {"covered_lines": covered, "num_statements": statements}}
            for path, (covered, statements) in files.items()
        }
    }
    coverage_json = tmp_path / "coverage.json"
    coverage_json.write_text(json.dumps(report), encoding="utf-8")
    return ["check_coverage_gates.py", "--pyproject", str(pyproject), "--coverage-json", str(coverage_json)]


TABLE = '[tool.bank.coverage-gates]\n"pkg/domain" = 90\n"pkg/api/" = 80\n"pkg/empty" = 90\n'


def test_passes_when_every_gate_is_met(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    argv = _write_inputs(
        tmp_path, TABLE, {"pkg/domain/money.py": (9, 10), "pkg/domain/case.py": (10, 10), "pkg/api/app.py": (8, 10)}
    )

    assert gates.main(argv) == 0
    output = capsys.readouterr().out
    assert "PASS  pkg/domain: 95.0% of 20 statements (gate 90%)" in output
    assert "PASS  pkg/api: 80.0% of 10 statements (gate 80%)" in output
    assert "PASS  pkg/empty: no statements yet (gate 90%)" in output


def test_fails_when_a_gate_is_missed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    argv = _write_inputs(tmp_path, TABLE, {"pkg/domain/money.py": (8, 10), "pkg/api/app.py": (10, 10)})

    assert gates.main(argv) == 1
    captured = capsys.readouterr()
    assert "FAIL  pkg/domain: 80.0% of 10 statements (gate 90%)" in captured.out
    assert "1 of 3 gate(s) failed" in captured.err


def test_prefixes_match_whole_path_segments_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    argv = _write_inputs(tmp_path, TABLE, {"pkg/domainless/x.py": (0, 10)})

    assert gates.main(argv) == 0
    assert "PASS  pkg/domain: no statements yet" in capsys.readouterr().out


def test_missing_gate_table_is_an_input_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    argv = _write_inputs(tmp_path, "[tool.other]\nx = 1\n", {})

    assert gates.main(argv) == 2
    assert "no [tool.bank.coverage-gates] table" in capsys.readouterr().err


@pytest.mark.parametrize("value", ["101", "-1", '"ninety"', "true"])
def test_invalid_gate_values_are_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str], value: str) -> None:
    argv = _write_inputs(tmp_path, f'[tool.bank.coverage-gates]\n"pkg" = {value}\n', {})

    assert gates.main(argv) == 2
    assert "must be a number between 0 and 100" in capsys.readouterr().err


def test_missing_or_malformed_report_is_an_input_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    argv = _write_inputs(tmp_path, TABLE, {})
    Path(argv[-1]).write_text('{"not": "a report"}', encoding="utf-8")

    assert gates.main(argv) == 2
    assert "is not a coverage.py JSON report" in capsys.readouterr().err

    Path(argv[-1]).unlink()
    assert gates.main(argv) == 2
    assert "cannot read" in capsys.readouterr().err
