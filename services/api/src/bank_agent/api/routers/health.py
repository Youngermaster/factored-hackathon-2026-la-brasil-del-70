"""Liveness and readiness endpoints."""

import asyncio
from typing import Literal

import structlog
from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from bank_agent.api.provider import ApiConfig, ServiceProvider
from bank_agent.ports.health import ReadinessCheck

router = APIRouter(prefix="/health", tags=["health"])
_logger = structlog.get_logger(__name__)

CheckStatus = Literal["ok", "unavailable"]


class LivenessResponse(BaseModel):
    status: Literal["live"] = "live"


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, CheckStatus]


async def _run_check(check: ReadinessCheck, timeout_seconds: float) -> CheckStatus:
    try:
        async with asyncio.timeout(timeout_seconds):
            healthy = await check.check()
    except TimeoutError:
        _logger.warning("readiness_check_timed_out", check=check.name, timeout_seconds=timeout_seconds)
        return "unavailable"
    except Exception as exc:  # a failing dependency must never crash the probe
        _logger.warning("readiness_check_failed", check=check.name, error_type=type(exc).__name__)
        return "unavailable"
    return "ok" if healthy else "unavailable"


@router.get("/live", response_model=LivenessResponse)
async def live() -> LivenessResponse:
    """The process is up and serving requests."""
    return LivenessResponse()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
async def ready(request: Request, response: Response) -> ReadinessResponse:
    """Every configured dependency is reachable. Failures report the check name only, never error text."""
    provider: ServiceProvider = request.app.state.provider
    checks = list(provider.readiness_checks)
    config: ApiConfig = request.app.state.api_config
    timeout_seconds = config.readiness_timeout_seconds
    results = await asyncio.gather(*(_run_check(check, timeout_seconds) for check in checks))
    outcome = {check.name: result for check, result in zip(checks, results, strict=True)}
    if all(result == "ok" for result in results):
        return ReadinessResponse(status="ready", checks=outcome)
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="not_ready", checks=outcome)
