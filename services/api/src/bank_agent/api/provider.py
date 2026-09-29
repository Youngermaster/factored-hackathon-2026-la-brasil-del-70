"""What the HTTP layer needs from the composition root, expressed as a Protocol.

``bank_agent.api`` and ``bank_agent.bootstrap`` are independent layers, so the API never imports the
container. The container in ``bootstrap/container.py`` satisfies this Protocol structurally, and the entry
point in ``bank_agent.asgi`` passes it to ``create_app`` together with an ``ApiConfig`` built from settings.
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from bank_agent.api.config import SecurityConfig
from bank_agent.application.agent.inbox import AgentInbox
from bank_agent.application.conversations.service import ConversationService
from bank_agent.application.identity.sessions import SessionService
from bank_agent.application.preferences.service import AssistantPreferencesService
from bank_agent.ports.determinism import Clock
from bank_agent.ports.evaluation import EvaluationSummaryReader
from bank_agent.ports.health import ReadinessCheck


@dataclass(frozen=True, slots=True)
class ApiConfig:
    """HTTP-layer configuration derived from settings by the composition root."""

    request_id_factory: Callable[[], str]
    version: str
    title: str = "bank-agent"
    expose_docs: bool = True
    readiness_timeout_seconds: float = 2.0
    security: SecurityConfig = field(default_factory=SecurityConfig.development)
    monotonic: Callable[[], float] = time.monotonic
    """The clock of the rate limiter's windows; tests pass a controllable one."""


class ServiceProvider(Protocol):
    """Services the HTTP layer resolves: identity, conversations, the agent inbox, and evaluation summaries."""

    @property
    def clock(self) -> Clock:
        """The clock sessions and cookies are computed against."""
        ...

    @property
    def session_service(self) -> SessionService | None:
        """Login, step-up, and sessions; ``None`` until ``SESSION_SECRET`` is set (auth routes answer 503)."""
        ...

    @property
    def conversations(self) -> ConversationService: ...

    @property
    def assistant_preferences(self) -> AssistantPreferencesService: ...

    @property
    def inbox(self) -> AgentInbox: ...

    @property
    def evaluation_summaries(self) -> EvaluationSummaryReader: ...

    @property
    def readiness_checks(self) -> Sequence[ReadinessCheck]:
        """Dependencies checked by ``/health/ready``; empty when none are configured."""
        ...

    async def aclose(self) -> None:
        """Release pooled resources such as database engines. Called once at application shutdown."""
        ...
