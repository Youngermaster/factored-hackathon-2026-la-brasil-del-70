import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPOSITORY_ROOT / "scripts" / "write_fixture_cassettes.py"
COMMITTED = REPOSITORY_ROOT / "evals" / "cassettes"
RECORDINGS = COMMITTED / "eval"  # evaluation run recordings (session 14b), not hand-authored fixtures


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("write_fixture_cassettes", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["write_fixture_cassettes"] = module
    spec.loader.exec_module(module)
    return module


def test_committed_fixture_cassettes_are_current() -> None:
    assert _load().main(["--check"]) == 0


def test_writing_reproduces_the_committed_files_exactly(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    module = _load()

    assert module.main(["--output-dir", str(tmp_path)]) == 0

    written = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*.json"))
    committed = sorted(
        path.relative_to(COMMITTED) for path in COMMITTED.rglob("*.json") if not path.is_relative_to(RECORDINGS)
    )
    assert written == committed
    for relative in written:
        assert (tmp_path / relative).read_bytes() == (COMMITTED / relative).read_bytes()
    assert f"wrote {len(written)} fixture cassettes" in capsys.readouterr().out


def test_check_names_stale_and_missing_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    module = _load()
    module.main(["--output-dir", str(tmp_path)])
    first, second = sorted(tmp_path.rglob("*.json"))[:2]
    first.write_text("{}\n", encoding="utf-8")
    second.unlink()

    assert module.main(["--check", "--output-dir", str(tmp_path)]) == 1

    errors = capsys.readouterr().err
    assert str(first.relative_to(tmp_path)) in errors
    assert str(second.relative_to(tmp_path)) in errors


def test_every_fixture_is_labeled_hand_authored() -> None:
    module = _load()

    for case in module.fixture_cases():
        _, cassette = module.build(case)
        assert cassette.provenance.value == "hand_authored_fixture"
        assert cassette.model_id == "fixture/hand-authored"
        assert cassette.labels["case"] in {"normal", "ambiguous", "out_of_scope"}
