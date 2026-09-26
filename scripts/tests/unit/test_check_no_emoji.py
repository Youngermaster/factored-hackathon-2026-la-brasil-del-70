import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "checks" / "check_no_emoji.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_no_emoji", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_no_emoji"] = module
    spec.loader.exec_module(module)
    return module


emoji = _load()
GRINNING_FACE = chr(0x1F600)
CHECK_MARK = chr(0x2705)


def test_reports_each_emoji_with_its_position(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    offending = tmp_path / "notes.md"
    offending.write_text(f"fine line\nbad {GRINNING_FACE} and {CHECK_MARK}\n", encoding="utf-8")

    assert emoji.main(["check_no_emoji.py", str(offending)]) == 1
    output = capsys.readouterr()
    assert f"{offending}:2:5: emoji character U+1F600 is not allowed" in output.out
    assert f"{offending}:2:11: emoji character U+2705 is not allowed" in output.out
    assert "2 emoji character(s) found" in output.err


def test_clean_text_passes(tmp_path: Path) -> None:
    clean = tmp_path / "clean.md"
    clean.write_text("Disputa registrada. Contestacao registrada. Accents are fine: a e i o u n.\n", encoding="utf-8")

    assert emoji.main(["check_no_emoji.py", str(clean)]) == 0


def test_binary_and_missing_files_are_skipped(tmp_path: Path) -> None:
    binary = tmp_path / "image.bin"
    binary.write_bytes(b"\x00\x01" + GRINNING_FACE.encode("utf-8"))

    assert emoji.main(["check_no_emoji.py", str(binary), str(tmp_path / "absent.txt")]) == 0


@pytest.mark.parametrize(
    "path",
    [
        ".claude/skills/x/SKILL.md",
        "kit/prompts/01.md",
        "apps/web/node_modules/pkg/a.js",
        "uv.lock",
        "apps/web/pnpm-lock.yaml",
        "data/raw/x.csv",
    ],
)
def test_vendored_and_generated_paths_are_excluded(path: str) -> None:
    assert emoji.is_excluded(path)


def test_authored_paths_are_checked() -> None:
    assert not emoji.is_excluded("services/api/README.md")
