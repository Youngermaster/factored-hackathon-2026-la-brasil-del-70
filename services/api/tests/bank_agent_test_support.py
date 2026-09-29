"""Test doubles shared by bank_agent tests. Importable because pytest adds services/api/tests to the path."""

import asyncio
import itertools
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from bank_agent.api.config import SecurityConfig
from bank_agent.api.provider import ApiConfig
from bank_agent.application.agent.inbox import AgentInbox
from bank_agent.application.conversations.service import ConversationService
from bank_agent.application.identity.sessions import SessionService
from bank_agent.application.profile.service import ProfileService
from bank_agent.ports.evaluation import EvaluationSummaryReader
from bank_agent.ports.health import ReadinessCheck
from bank_agent.testing.clock import FixedClock


class StaticReadinessCheck:
    """Readiness check with a fixed outcome."""

    def __init__(self, name: str, healthy: bool) -> None:
        self._name = name
        self._healthy = healthy

    @property
    def name(self) -> str:
        return self._name

    async def check(self) -> bool:
        return self._healthy


class RaisingReadinessCheck:
    """Readiness check whose dependency raises an unexpected error."""

    def __init__(self, name: str, message: str) -> None:
        self._name = name
        self._message = message

    @property
    def name(self) -> str:
        return self._name

    async def check(self) -> bool:
        raise RuntimeError(self._message)


class HangingReadinessCheck:
    """Readiness check that never answers within the timeout."""

    @property
    def name(self) -> str:
        return "slow"

    async def check(self) -> bool:
        await asyncio.Event().wait()
        return True


class FakeProvider:
    """ServiceProvider for the health and middleware tests: configurable readiness checks, recorded shutdown.

    It has no identity service (auth routes answer 503) and fails loudly if a test reaches for the conversation,
    profile, inbox, or evaluation services, which the API tests take from a real container instead.
    """

    def __init__(self, checks: Sequence[ReadinessCheck] = ()) -> None:
        self._checks = tuple(checks)
        self.closed = False
        self._clock = FixedClock(datetime(2026, 6, 18, 15, 0, tzinfo=UTC))

    @property
    def readiness_checks(self) -> Sequence[ReadinessCheck]:
        return self._checks

    @property
    def clock(self) -> FixedClock:
        return self._clock

    @property
    def session_service(self) -> SessionService | None:
        return None

    @property
    def conversations(self) -> ConversationService:
        raise AssertionError("FakeProvider has no conversation service")

    @property
    def profiles(self) -> ProfileService:
        raise AssertionError("FakeProvider has no profile service")

    @property
    def inbox(self) -> AgentInbox:
        raise AssertionError("FakeProvider has no agent inbox")

    @property
    def evaluation_summaries(self) -> EvaluationSummaryReader:
        raise AssertionError("FakeProvider has no evaluation summaries")

    async def aclose(self) -> None:
        self.closed = True


class SequentialIds:
    """Deterministic request id factory: req-00000001, req-00000002, ..."""

    def __init__(self) -> None:
        self._counter = itertools.count(1)

    def __call__(self) -> str:
        return f"req-{next(self._counter):08d}"


def api_config(
    timeout_seconds: float = 2.0, expose_docs: bool = True, security: SecurityConfig | None = None
) -> ApiConfig:
    return ApiConfig(
        request_id_factory=SequentialIds(),
        version="0.0.0-test",
        expose_docs=expose_docs,
        readiness_timeout_seconds=timeout_seconds,
        security=security or SecurityConfig.development(),
    )


@dataclass(frozen=True)
class PostgresInstance:
    """Connection facts for the integration-test PostgreSQL container. Passwords are generated per session."""

    host: str
    port: int
    database: str
    owner: str
    owner_password: str
    app_user: str
    app_password: str
