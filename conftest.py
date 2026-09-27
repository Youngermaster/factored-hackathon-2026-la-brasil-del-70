"""Repository-wide pytest hooks.

Every test is classified by the directory it lives in:

- ``tests/unit/``: marked ``unit`` and run with the network disabled (pytest-socket). Unix sockets stay
  allowed through ``--allow-unix-socket`` because the asyncio event loop uses a socket pair internally.
- ``tests/integration/``: marked ``integration``; sockets are allowed so tests can reach PostgreSQL.

A test outside both directories must carry an explicit ``unit`` or ``integration`` marker (for example a
parameterized contract test), otherwise collection fails. No test escapes classification.
"""

from pathlib import Path

import pytest

# Shared PostgreSQL fixtures (one migrated container per session) for the service and data platform suites.
from bank_agent_postgres import migrated_postgres, postgres  # noqa: F401

_DIRECTORY_MARKERS = {"unit": pytest.mark.unit, "integration": pytest.mark.integration}


def _marker_from_path(path: Path) -> str | None:
    parts = path.parts
    for index, part in enumerate(parts[:-1]):
        if part == "tests" and index + 1 < len(parts) and parts[index + 1] in _DIRECTORY_MARKERS:
            return parts[index + 1]
    return None


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    unclassified: list[str] = []
    for item in items:
        directory_marker = _marker_from_path(Path(item.path))
        if directory_marker is not None:
            item.add_marker(_DIRECTORY_MARKERS[directory_marker])
        if item.get_closest_marker("unit") is not None:
            item.add_marker(pytest.mark.disable_socket)
        elif item.get_closest_marker("integration") is None:
            unclassified.append(item.nodeid)
    if unclassified:
        listing = "\n  ".join(unclassified)
        raise pytest.UsageError(
            "every test must live under tests/unit/ or tests/integration/, or carry an explicit "
            f"unit or integration marker; unclassified:\n  {listing}"
        )
