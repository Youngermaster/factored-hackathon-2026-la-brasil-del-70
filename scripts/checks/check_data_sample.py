"""Guard for the committed organizer data sample (CLAUDE.md rule 5). Stdlib only; run by `make check` and CI.

Fails when:
- the sample holds more than 5,000 data rows in total (sample files plus the preview);
- a table that has files is missing from the README row counts, or a count there differs from the files;
- the README is missing or lacks a required section;
- any file other than the README and CSV data files appears.

Usage: check_data_sample.py [sample directory] (default data_platform/sample).
"""

import csv
import re
import sys
from pathlib import Path

ROW_LIMIT = 5_000
REQUIRED_SECTIONS = (
    "## Source",
    "## Dataset version",
    "## Extraction",
    "## Row counts",
    "## Column treatments",
    "## Data-use terms",
)
PREVIEW_DIR = "preview"
DEFAULT_DIR = Path(__file__).resolve().parents[2] / "data_platform" / "sample"
_COUNT_ROW = re.compile(r"^\|\s*([a-z][a-z0-9_]*)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*$")


def count_rows(path: Path) -> int:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = sum(1 for _ in csv.reader(handle))
    return max(rows - 1, 0)


def table_of(relative: Path) -> str:
    return relative.parts[0].removesuffix(".csv")


def readme_counts(text: str) -> dict[str, tuple[int, int]]:
    section = text.split("## Row counts", 1)[1].split("\n## ", 1)[0] if "## Row counts" in text else ""
    counts: dict[str, tuple[int, int]] = {}
    for line in section.splitlines():
        match = _COUNT_ROW.match(line.strip())
        if match:
            counts[match[1]] = (int(match[2]), int(match[3]))
    return counts


def check(sample_dir: Path) -> list[str]:
    problems: list[str] = []
    if not sample_dir.is_dir():
        return [f"{sample_dir}: sample directory is missing"]
    readme = sample_dir / "README.md"
    if not readme.is_file():
        problems.append(f"{readme}: README is missing")
        text = ""
    else:
        text = readme.read_text(encoding="utf-8")
        problems += [f"{readme}: missing section '{section}'" for section in REQUIRED_SECTIONS if section not in text]

    sample: dict[str, int] = {}
    preview: dict[str, int] = {}
    for path in sorted(item for item in sample_dir.rglob("*") if item.is_file()):
        relative = path.relative_to(sample_dir)
        if relative == Path("README.md"):
            continue
        if path.suffix != ".csv":
            problems.append(f"{relative}: unexpected file type (only CSV data files and README.md are allowed)")
            continue
        if relative.parts[0] == PREVIEW_DIR:
            name = relative.stem
            preview[name] = preview.get(name, 0) + count_rows(path)
        else:
            name = table_of(relative)
            sample[name] = sample.get(name, 0) + count_rows(path)

    listed = readme_counts(text)
    for name in sorted(set(sample) | set(preview)):
        if name not in listed:
            problems.append(f"{readme}: table '{name}' is missing from the row counts")
        elif listed[name] != (sample.get(name, 0), preview.get(name, 0)):
            problems.append(
                f"{readme}: row counts for '{name}' say {listed[name]}, files hold "
                f"{(sample.get(name, 0), preview.get(name, 0))}"
            )
    total = sum(sample.values()) + sum(preview.values())
    if total > ROW_LIMIT:
        problems.append(f"{sample_dir}: {total} data rows, above the limit of {ROW_LIMIT}")
    return problems


def main(argv: list[str]) -> int:
    sample_dir = Path(argv[1]) if len(argv) > 1 else DEFAULT_DIR
    problems = check(sample_dir)
    for problem in problems:
        print(problem)
    if problems:
        print(f"check-data-sample: {len(problems)} problem(s)", file=sys.stderr)
        return 1
    print("check-data-sample: sample within bounds and documented")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
