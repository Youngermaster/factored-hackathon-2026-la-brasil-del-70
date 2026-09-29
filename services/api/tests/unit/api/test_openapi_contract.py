"""The committed OpenAPI contract: fresh, with stable operation ids, and with documented roles that match the code."""

import json
from pathlib import Path
from typing import Any

from fastapi.routing import APIRoute

from bank_agent import __version__
from bank_agent.api.app import create_app
from bank_agent.api.dependencies import ANYONE
from bank_agent.api.openapi import build_schema_app, render
from bank_agent.api.routers import agent, auth, conversations, evaluation, health, preferences

COMMITTED = Path(__file__).resolve().parents[5] / "contracts" / "openapi.json"
OPERATION_IDS = {
    "auth_csrf", "auth_start", "auth_verify", "auth_step_up_start", "auth_step_up_verify", "auth_logout", "auth_me",
    "conversations_create", "conversations_send_turn", "conversations_get", "conversations_trace",
    "agent_list_handoffs", "agent_get_handoff", "agent_claim_handoff", "agent_resolve_handoff",
    "agent_list_credit_applications", "agent_get_credit_application",
    "eval_list_summaries", "eval_conversation_trace", "health_live", "health_ready", "health_details",
    "assistant_profile_get", "assistant_profile_name_set", "assistant_profile_image_change",
}  # fmt: skip


def document() -> dict[str, Any]:
    return build_schema_app(create_app, __version__).openapi()


def operations(spec: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    return [(method, path, op) for path, item in spec["paths"].items() for method, op in item.items()]


def test_the_committed_document_is_current() -> None:
    assert COMMITTED.read_text(encoding="utf-8") == render(document()), "stale contract: run make openapi"


def test_every_operation_has_its_stable_id_and_the_security_extensions() -> None:
    spec = document()
    ids = [op["operationId"] for _, _, op in operations(spec)]
    assert len(ids) == len(set(ids))
    assert set(ids) == OPERATION_IDS
    for method, path, op in operations(spec):
        if path.startswith("/v1"):
            assert {"x-roles", "x-rate-limit", "x-csrf"} <= set(op), path
            assert op["x-csrf"] is (method != "get"), path
        assert "default" in op["responses"], path


def test_the_roles_each_route_enforces_are_the_roles_it_documents() -> None:
    for module in (auth, conversations, agent, evaluation, preferences):
        for route in module.router.routes:
            assert isinstance(route, APIRoute)
            enforced = {
                tuple(sorted(role.value for role in dependency.call.roles))  # type: ignore[union-attr]
                for dependency in route.dependant.dependencies
                if hasattr(dependency.call, "roles")
            }
            documented = (route.openapi_extra or {})["x-roles"]
            assert enforced == (set() if documented == [ANYONE] else {tuple(documented)}), route.path
    assert all(isinstance(route, APIRoute) and route.openapi_extra is None for route in health.router.routes)


def test_validation_errors_are_documented_as_problem_details() -> None:
    spec = document()
    assert "HTTPValidationError" not in spec["components"]["schemas"]
    responses = spec["paths"]["/v1/conversations/{conversation_id}/turns"]["post"]["responses"]
    assert set(responses["422"]["content"]) == {"application/problem+json"}
    assert json.dumps(spec).count("csrfHeader") > 1
