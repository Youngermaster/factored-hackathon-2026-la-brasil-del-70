"""The OpenAPI document: FastAPI's schema plus the security schemes and RFC 9457 problem responses.

``contracts/openapi.json`` is this document, exported by ``scripts/export_openapi.py`` (``make openapi``) from an
app built with ``SchemaOnlyProvider``; a test fails when the committed file is stale. Every operation has an
explicit, stable ``operationId`` and the ``x-roles``, ``x-rate-limit``, and ``x-csrf`` extensions from
``dependencies.endpoint``. Validation errors are documented as problem details, which is what the API returns.
"""

import copy
import json
from collections.abc import Callable, Sequence
from typing import Any, Final

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from bank_agent.api.csrf import CSRF_HEADER
from bank_agent.api.dependencies import ANYONE
from bank_agent.api.problems import PROBLEM_CONTENT_TYPE
from bank_agent.api.provider import ApiConfig
from bank_agent.application.agent.inbox import AgentInbox
from bank_agent.application.conversations.service import ConversationService
from bank_agent.application.identity.sessions import SessionService
from bank_agent.ports.determinism import Clock
from bank_agent.ports.evaluation import EvaluationSummaryReader
from bank_agent.ports.health import ReadinessCheck

PROBLEM_REF: Final = {"$ref": "#/components/schemas/ProblemDetails"}
PROBLEM_SCHEMA: Final[dict[str, Any]] = {
    "title": "ProblemDetails",
    "description": "RFC 9457 problem details. `type` is a stable URI per error; `errors` lists invalid fields.",
    "type": "object",
    "required": ["type", "title", "status", "instance"],
    "properties": {
        "type": {"type": "string", "format": "uri"},
        "title": {"type": "string"},
        "status": {"type": "integer"},
        "detail": {"type": "string"},
        "instance": {"type": "string"},
        "request_id": {"type": "string"},
        "errors": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["loc", "type"],
                "properties": {"loc": {"type": "array", "items": {"type": "string"}}, "type": {"type": "string"}},
            },
        },
    },
}
SECURITY_SCHEMES: Final[dict[str, Any]] = {
    "sessionCookie": {
        "type": "apiKey",
        "in": "cookie",
        "name": "__Host-session",
        "description": "Opaque session token (HttpOnly). The development cookie is named `session`.",
    },
    "csrfHeader": {
        "type": "apiKey",
        "in": "header",
        "name": CSRF_HEADER,
        "description": "The double-submit token from `GET /v1/auth/csrf`, echoed on every state-changing request.",
    },
}


class SchemaOnlyProvider:
    """A ``ServiceProvider`` for exporting the schema: it serves no request."""

    readiness_checks: Sequence[ReadinessCheck] = ()

    def _unavailable(self) -> RuntimeError:
        return RuntimeError("the schema-only provider serves no requests")

    @property
    def clock(self) -> Clock:
        raise self._unavailable()

    @property
    def session_service(self) -> SessionService | None:
        return None

    @property
    def conversations(self) -> ConversationService:
        raise self._unavailable()

    @property
    def inbox(self) -> AgentInbox:
        raise self._unavailable()

    @property
    def evaluation_summaries(self) -> EvaluationSummaryReader:
        raise self._unavailable()

    async def aclose(self) -> None:
        return None


def _security(operation: dict[str, Any]) -> list[dict[str, list[str]]]:
    signed_in = operation.get("x-roles", [ANYONE]) != [ANYONE]
    requirement: dict[str, list[str]] = {}
    if signed_in:
        requirement["sessionCookie"] = []
    if operation.get("x-csrf"):
        requirement["csrfHeader"] = []
    return [requirement] if requirement else []


def _problem_responses(operation: dict[str, Any]) -> None:
    responses: dict[str, Any] = operation.setdefault("responses", {})
    problem = {"description": "Problem details (RFC 9457)", "content": {PROBLEM_CONTENT_TYPE: {"schema": PROBLEM_REF}}}
    if "422" in responses:
        responses["422"] = {**problem, "description": "Validation error as problem details"}
    responses["default"] = problem


def enrich(document: dict[str, Any]) -> dict[str, Any]:
    """Add the security schemes, per-operation security, and problem responses to FastAPI's document."""
    enriched = copy.deepcopy(document)
    components = enriched.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    schemas.pop("HTTPValidationError", None)
    schemas.pop("ValidationError", None)
    schemas["ProblemDetails"] = PROBLEM_SCHEMA
    components["securitySchemes"] = SECURITY_SCHEMES
    for path_item in enriched.get("paths", {}).values():
        for operation in path_item.values():
            operation["security"] = _security(operation)
            _problem_responses(operation)
    return enriched


def install_openapi(app: FastAPI) -> None:
    """Serve the enriched document at ``/openapi.json`` (development only) and from ``app.openapi()``."""

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            base = get_openapi(title=app.title, version=app.version, routes=app.routes, description=app.description)
            app.openapi_schema = enrich(base)
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]


def render(document: dict[str, Any]) -> str:
    """The committed form: sorted keys, two-space indent, a trailing newline, non-ASCII kept."""
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def build_schema_app(create: Callable[..., FastAPI], version: str) -> FastAPI:
    """An app for the export, from ``create_app`` and a schema-only provider (no settings, no database)."""
    return create(SchemaOnlyProvider(), ApiConfig(request_id_factory=lambda: "schema-export", version=version))
