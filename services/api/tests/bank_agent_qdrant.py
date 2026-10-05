"""Qdrant for integration and contract tests: one container per test session, with the production hardening.

The image is the one pinned in ``deploy/compose.prod.yml`` (the unprivileged variant, by digest), started with a
read-only root, every capability dropped, no-new-privileges, and tmpfs mounts for the paths it writes, so a test
pass also shows that the production service definition can run. Telemetry is off. The fixture is a factory
(``qdrant_url``) used only by tests marked ``integration``.
"""

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import HttpWaitStrategy

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
QDRANT_PORT = 6333


def compose_qdrant_image() -> str:
    """The Qdrant image pinned in deploy/compose.prod.yml, so tests and production never drift."""
    compose = (REPOSITORY_ROOT / "deploy" / "compose.prod.yml").read_text(encoding="utf-8")
    match = re.search(r"^\s+image:\s+(qdrant/qdrant:\S+)\s*$", compose, flags=re.MULTILINE)
    if match is None:
        raise AssertionError("deploy/compose.prod.yml pins no qdrant image")
    return match[1]


@pytest.fixture(scope="session")
def qdrant_url() -> Iterator[str]:
    container = (
        DockerContainer(compose_qdrant_image())
        .with_exposed_ports(QDRANT_PORT)
        .with_env("QDRANT__TELEMETRY_DISABLED", "true")
        .with_env("QDRANT_INIT_FILE_PATH", "/qdrant/init/.qdrant-initialized")
        .with_kwargs(
            read_only=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            user="1000:1000",
        )
        .waiting_for(HttpWaitStrategy(QDRANT_PORT, "/readyz").for_status_code(200))
    )
    # Mount options per path (docker's tmpfs mapping); the storage volumes are tmpfs here, named volumes in production.
    container.tmpfs.update(
        {
            "/tmp": "uid=1000,gid=1000,size=64m",  # noqa: S108 - a tmpfs inside the container
            "/qdrant/init": "uid=1000,gid=1000,size=1m",
            "/qdrant/storage": "uid=1000,gid=1000,size=256m",
            "/qdrant/snapshots": "uid=1000,gid=1000,size=16m",
        }
    )
    with container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(QDRANT_PORT)
        yield f"http://{host}:{port}"
