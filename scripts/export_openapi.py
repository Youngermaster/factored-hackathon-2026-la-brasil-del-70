#!/usr/bin/env python3
"""Export the API's OpenAPI document to ``contracts/openapi.json``.

Usage:
    uv run --frozen python scripts/export_openapi.py            write the document
    uv run --frozen python scripts/export_openapi.py --check    exit 1 when the committed document is stale

The app is built with a schema-only provider, so the export needs no settings, database, or secrets. ``make openapi``
runs this and then regenerates the TypeScript types in ``apps/web/src/shared/api/generated/schema.d.ts``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bank_agent import __version__
from bank_agent.api.app import create_app
from bank_agent.api.openapi import build_schema_app, render

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPOSITORY_ROOT / "contracts" / "openapi.json"


def document_text() -> str:
    return render(build_schema_app(create_app, __version__).openapi())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--check", action="store_true", help="fail when the committed document is stale")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args(argv)
    text = document_text()
    if arguments.check:
        current = arguments.output.read_text(encoding="utf-8") if arguments.output.is_file() else ""
        if current != text:
            print(f"stale: {arguments.output}; run make openapi", file=sys.stderr)
            return 1
        return 0
    arguments.output.write_text(text, encoding="utf-8")
    print(f"wrote {arguments.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
