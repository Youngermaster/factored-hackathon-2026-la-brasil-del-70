"""Test doubles shared by bank_agent tests. Importable because pytest adds services/api/tests to the path."""

import asyncio
import itertools
from collections.abc import Sequence

from bank_agent.api.provider import ApiConfig
from bank_agent.ports.health import ReadinessCheck


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
    """ServiceProvider with configurable readiness checks that records shutdown."""

    def __init__(self, checks: Sequence[ReadinessCheck] = ()) -> None:
        self._checks = tuple(checks)
        self.closed = False

    @property
    def readiness_checks(self) -> Sequence[ReadinessCheck]:
        return self._checks

    async def aclose(self) -> None:
        self.closed = True


class SequentialIds:
    """Deterministic request id factory: req-00000001, req-00000002, ..."""

    def __init__(self) -> None:
        self._counter = itertools.count(1)

    def __call__(self) -> str:
        return f"req-{next(self._counter):08d}"


def api_config(timeout_seconds: float = 2.0, expose_docs: bool = True) -> ApiConfig:
    return ApiConfig(
        request_id_factory=SequentialIds(),
        version="0.0.0-test",
        expose_docs=expose_docs,
        readiness_timeout_seconds=timeout_seconds,
    )
