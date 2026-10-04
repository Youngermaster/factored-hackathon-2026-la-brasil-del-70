from datetime import timedelta

import httpx
import pytest
from fastapi import APIRouter

from bank_agent.api.app import create_app
from bank_agent.api.domain_problems import domain_problem_registry
from bank_agent.api.problems import PROBLEM_CONTENT_TYPE
from bank_agent.domain import errors
from bank_agent.domain.errors import DomainError, all_error_types
from bank_agent_test_support import FakeProvider, api_config


def _instance(error_type: type[DomainError]) -> DomainError:
    if error_type is errors.SessionExpiredError:
        return errors.SessionExpiredError("idle")
    if error_type is errors.IdentityLockedError:
        return errors.IdentityLockedError(timedelta(minutes=5))
    if error_type is errors.ConversationCreationLimitedError:
        return errors.ConversationCreationLimitedError(timedelta(hours=1))
    return error_type()


TAXONOMY = [t for t in all_error_types() if t is not DomainError and t.__module__ == "bank_agent.domain.errors"]


@pytest.mark.parametrize("error_type", TAXONOMY, ids=lambda t: t.__name__)
def test_every_domain_error_maps_to_a_problem(error_type: type[DomainError]) -> None:
    assert domain_problem_registry().problem_for(_instance(error_type)) is not None


@pytest.mark.parametrize(
    ("error", "status", "slug"),
    [
        (errors.ConversationCreationLimitedError(timedelta(hours=1)), 429, "conversation-creation-limited"),
        (errors.CaseNotFoundError(), 404, "resource-not-found"),
        (errors.SessionExpiredError("absolute"), 401, "session-expired"),
        (errors.IdentityChallengeFailedError(), 401, "authentication-required"),
        (errors.StepUpRequiredError(), 403, "step-up-required"),
        (errors.InsufficientAuthLevelError(), 403, "action-not-permitted"),
        (errors.AccessContextError(), 500, "internal-error"),
        (errors.IdempotencyConflictError(), 409, "conflict"),
        (errors.InvalidCaseTransitionError(), 409, "invalid-state-transition"),
        (errors.CurrencyMismatchError(), 422, "unprocessable-request"),
        (errors.LlmTimeoutError(), 503, "dependency-unavailable"),
        (errors.PromptNotFoundError(), 500, "internal-error"),
    ],
)
def test_family_mapping(error: DomainError, status: int, slug: str) -> None:
    problem = domain_problem_registry().problem_for(error)
    assert problem is not None
    assert (problem.status, problem.slug) == (status, slug)


async def test_the_default_app_renders_domain_errors_without_leaking_messages() -> None:
    app = create_app(FakeProvider(), api_config())
    router = APIRouter()

    @router.get("/cases/{case_id}")
    async def get_case(case_id: str) -> dict[str, str]:
        raise errors.CaseNotFoundError(f"case {case_id} of customer CUS-B-0002")

    app.include_router(router)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/cases/case-9")

    assert response.status_code == 404
    assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
    body = response.json()
    assert body["type"] == "https://bank-agent.local/problems/resource-not-found"
    assert "CUS-B-0002" not in response.text
    assert "detail" not in body
