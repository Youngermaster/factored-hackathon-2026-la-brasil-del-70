"""The endpoint catalog in docs/api/README.md matches the OpenAPI document: paths, roles, CSRF, and rate class."""

import re
from pathlib import Path

from bank_agent import __version__
from bank_agent.api.app import create_app
from bank_agent.api.openapi import build_schema_app

CATALOG = Path(__file__).resolve().parents[5] / "docs" / "api" / "README.md"
ROW = re.compile(r"^\| (GET|POST) \| `([^`]+)` \| ([^|]+) \| (yes|no) \| (\w+) \|$")


def documented() -> dict[tuple[str, str], tuple[str, str, str]]:
    rows = {}
    for line in CATALOG.read_text(encoding="utf-8").splitlines():
        match = ROW.match(line)
        if match:
            method, path, roles, csrf, rate = match.groups()
            rows[(method.lower(), path)] = (roles.split(" (")[0].strip(), csrf, rate)
    return rows


def test_every_operation_is_in_the_catalog_with_its_roles_csrf_and_rate_class() -> None:
    spec = build_schema_app(create_app, __version__).openapi()
    expected = {}
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            roles = ", ".join(operation.get("x-roles", ["anyone"]))
            csrf = "yes" if operation.get("x-csrf") else "no"
            expected[(method, path)] = (roles, csrf, operation.get("x-rate-limit", "none"))
    assert documented() == expected
