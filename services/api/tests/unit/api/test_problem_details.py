import httpx
import pytest
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from bank_agent.api.app import create_app
from bank_agent.api.problems import PROBLEM_CONTENT_TYPE, ProblemRegistry, ProblemType
from bank_agent_test_support import FakeProvider, api_config


class CaseNotFoundError(Exception):
    """Stands in for a typed domain error."""


class ArchivedCaseNotFoundError(CaseNotFoundError):
    """A subclass must map through its registered base class."""


class DisputeRequest(BaseModel):
    description: str = Field(max_length=10)


def _client() -> httpx.AsyncClient:
    registry = ProblemRegistry()
    registry.register(CaseNotFoundError, ProblemType(404, "case-not-found", "Case not found"))
    app = create_app(FakeProvider(), api_config(), problems=registry)
    router = APIRouter()

    @router.post("/disputes")
    async def create_dispute(body: DisputeRequest) -> dict[str, str]:
        return {"description": body.description}

    @router.get("/cases/{case_id}")
    async def get_case(case_id: str) -> dict[str, str]:
        if case_id == "archived":
            raise ArchivedCaseNotFoundError(f"archived case {case_id} for customer 1020304050")
        raise CaseNotFoundError(f"case {case_id} belongs to customer 1020304050")

    @router.get("/forbidden")
    async def forbidden() -> dict[str, str]:
        raise HTTPException(status_code=429, detail="Too many attempts", headers={"Retry-After": "30"})

    @router.get("/boom")
    async def boom() -> dict[str, str]:
        raise RuntimeError("database password is hunter2-internal")

    app.include_router(router)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


async def test_unknown_route_returns_a_problem_document() -> None:
    async with _client() as client:
        response = await client.get("/missing", headers={"X-Request-ID": "client-abc-12345"})

    assert response.status_code == 404
    assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
    assert response.json() == {
        "type": "https://bank-agent.local/problems/not-found",
        "title": "Not Found",
        "status": 404,
        "instance": "/missing",
        "request_id": "client-abc-12345",
    }


async def test_validation_errors_list_locations_and_types_but_never_the_input() -> None:
    rejected = "this description is far too long 1020304050"
    async with _client() as client:
        response = await client.post("/disputes", json={"description": rejected})

    body = response.json()
    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
    assert body["type"] == "https://bank-agent.local/problems/validation-error"
    assert body["errors"] == [{"loc": ["body", "description"], "type": "string_too_long"}]
    assert rejected not in response.text


@pytest.mark.parametrize("case_id", ["c-1", "archived"])
async def test_registered_errors_map_to_their_problem_without_the_message(case_id: str) -> None:
    async with _client() as client:
        response = await client.get(f"/cases/{case_id}")

    assert response.status_code == 404
    assert response.json()["type"] == "https://bank-agent.local/problems/case-not-found"
    assert response.json()["title"] == "Case not found"
    assert "1020304050" not in response.text


async def test_http_exceptions_keep_their_detail_and_headers() -> None:
    async with _client() as client:
        response = await client.get("/forbidden")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "30"
    assert response.json()["detail"] == "Too many attempts"
    assert response.json()["type"] == "https://bank-agent.local/problems/too-many-requests"


async def test_unexpected_errors_return_a_generic_500_without_internals() -> None:
    async with _client() as client:
        response = await client.get("/boom")

    assert response.status_code == 500
    assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
    assert response.json()["type"] == "https://bank-agent.local/problems/internal-error"
    assert "hunter2" not in response.text
    assert "RuntimeError" not in response.text


def test_registering_the_same_error_twice_is_rejected() -> None:
    registry = ProblemRegistry()
    registry.register(CaseNotFoundError, ProblemType(404, "case-not-found", "Case not found"))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(CaseNotFoundError, ProblemType(404, "case-not-found", "Case not found"))


def test_unregistered_errors_have_no_problem_type() -> None:
    assert ProblemRegistry().problem_for(KeyError("x")) is None
