"""What the HTTP layer needs from the composition root, expressed as a Protocol.

``bank_agent.api`` and ``bank_agent.bootstrap`` are independent layers, so the API never imports the
container. The container in ``bootstrap/container.py`` satisfies this Protocol structurally, and the entry
point in ``bank_agent.asgi`` passes it to ``create_app`` together with an ``ApiConfig`` built from settings.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from bank_agent.ports.health import ReadinessCheck


@dataclass(frozen=True, slots=True)
class ApiConfig:
    """HTTP-layer configuration derived from settings by the composition root."""

    request_id_factory: Callable[[], str]
    version: str
    title: str = "bank-agent"
    expose_docs: bool = True
    readiness_timeout_seconds: float = 2.0


class ServiceProvider(Protocol):
    """Services the HTTP layer resolves. Later phases add repositories, workflows, and security services."""

    @property
    def readiness_checks(self) -> Sequence[ReadinessCheck]:
        """Dependencies checked by ``/health/ready``; empty when none are configured."""
        ...

    async def aclose(self) -> None:
        """Release pooled resources such as database engines. Called once at application shutdown."""
        ...
