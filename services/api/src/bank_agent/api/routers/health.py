"""Liveness, readiness, and the degradation details.

``/health/ready`` is the orchestrator's probe: 503 while a configured dependency (the database) is unreachable, which
is degradation level L4. ``/health/details`` is for people and dashboards: the ladder level, its reasons, and every
component's state, from the same probes plus the circuit breakers, the model budget, and the startup loads. Both
report names and codes only, never error text or connection details.
"""

import asyncio
from typing import Literal

import structlog
from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from bank_agent.api.provider import ApiConfig, ServiceProvider
from bank_agent.domain.degradation import ComponentState, DegradationLevel
from bank_agent.ports.health import ReadinessCheck

router = APIRouter(prefix="/health", tags=["health"])
_logger = structlog.get_logger(__name__)

CheckStatus = Literal["ok", "unavailable"]
DATABASE = "database"


class LivenessResponse(BaseModel):
    status: Literal["live"] = "live"


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, CheckStatus]


class HealthDetailsResponse(BaseModel):
    status: Literal["normal", "degraded", "unavailable"]
    level: Literal["L0", "L1", "L2", "L3", "L4"]
    reasons: tuple[str, ...]
    components: dict[str, ComponentState]
    checks: dict[str, CheckStatus]
    template_only: bool
    budget_used_ratio: float


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


async def _probe(request: Request) -> dict[str, CheckStatus]:
    """Run every readiness check and tell the degradation monitor what the database probe found."""
    provider: ServiceProvider = request.app.state.provider
    checks = list(provider.readiness_checks)
    config: ApiConfig = request.app.state.api_config
    timeout_seconds = config.readiness_timeout_seconds
    results = await asyncio.gather(*(_run_check(check, timeout_seconds) for check in checks))
    outcome = {check.name: result for check, result in zip(checks, results, strict=True)}
    if DATABASE in outcome:
        provider.degradation.record_database(outcome[DATABASE] == "ok")
    return outcome


@router.get("/live", response_model=LivenessResponse, operation_id="health_live")
async def live() -> LivenessResponse:
    """The process is up and serving requests."""
    return LivenessResponse()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
    operation_id="health_ready",
)
async def ready(request: Request, response: Response) -> ReadinessResponse:
    """Every configured dependency is reachable. Failures report the check name only, never error text."""
    outcome = await _probe(request)
    if all(result == "ok" for result in outcome.values()):
        return ReadinessResponse(status="ready", checks=outcome)
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="not_ready", checks=outcome)


@router.get(
    "/details",
    response_model=HealthDetailsResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthDetailsResponse}},
    operation_id="health_details",
)
async def details(request: Request, response: Response) -> HealthDetailsResponse:
    """The degradation level (L0 to L4), its reasons, and each component's state; 503 at L4."""
    checks = await _probe(request)
    provider: ServiceProvider = request.app.state.provider
    current = provider.degradation.current()
    health: Literal["normal", "degraded", "unavailable"] = "degraded" if current.degraded else "normal"
    if current.level is DegradationLevel.DATABASE_UNAVAILABLE:
        health = "unavailable"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthDetailsResponse(
        status=health,
        level=current.level.label,  # type: ignore[arg-type]
        reasons=current.reasons,
        components={component.value: state for component, state in current.components.items()},
        checks=checks,
        template_only=current.template_only,
        budget_used_ratio=round(current.budget_used_ratio, 4),
    )
