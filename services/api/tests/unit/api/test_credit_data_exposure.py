"""No customer-role response schema exposes a credit profile field, a risk estimate value, or an internal field.

The walk resolves every ``$ref`` of every 2xx response of every operation a customer may call (``x-roles`` naming
``customer`` or ``anyone``), nested at any depth, so a field added to a reused domain view later fails here.
"""

from typing import Any

from bank_agent import __version__
from bank_agent.api.app import create_app
from bank_agent.api.openapi import build_schema_app

FORBIDDEN = {
    "credit_score", "estimated_monthly_income", "monthly_income", "monthly_income_usd", "declared_monthly_income",
    "max_days_past_due", "days_past_due", "utilization", "credit_product_count", "tenure_months",
    "probability", "interval_low", "interval_high", "band", "risk", "risk_estimates", "requested_amount_to_income",
    "is_fraud", "fraud", "fraud_score", "trust_events", "evidence_text", "full_number", "document_number",
}  # fmt: skip
CUSTOMER_FACING = {"customer", "anyone"}


def _resolve(spec: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if ref is None:
        return schema
    resolved: dict[str, Any] = spec["components"]["schemas"][ref.rsplit("/", 1)[-1]]
    return resolved


def _walk(spec: dict[str, Any], schema: Any, seen: set[str], found: dict[str, set[str]], where: str) -> None:
    if isinstance(schema, list):
        for item in schema:
            _walk(spec, item, seen, found, where)
        return
    if not isinstance(schema, dict):
        return
    ref = schema.get("$ref")
    if isinstance(ref, str):
        if ref in seen:
            return
        seen.add(ref)
        _walk(spec, _resolve(spec, schema), seen, found, ref.rsplit("/", 1)[-1])
        return
    if schema.get("x-internal"):
        found.setdefault("x-internal", set()).add(where)
    for name, value in schema.get("properties", {}).items():
        found.setdefault(name, set()).add(where)
        _walk(spec, value, seen, found, where)
    for key in ("items", "anyOf", "oneOf", "allOf", "additionalProperties", "prefixItems"):
        if key in schema:
            _walk(spec, schema[key], seen, found, where)


def fields_of(spec: dict[str, Any], roles: set[str]) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for item in spec["paths"].values():
        for operation in item.values():
            if not roles & set(operation.get("x-roles", [])):
                continue
            for status, response in operation["responses"].items():
                if status.startswith("2"):
                    for media in response.get("content", {}).values():
                        _walk(spec, media["schema"], set(), found, operation["operationId"])
    return found


def test_customer_facing_schemas_carry_no_credit_profile_risk_or_internal_field() -> None:
    spec = build_schema_app(create_app, __version__).openapi()
    found = fields_of(spec, CUSTOMER_FACING)
    leaks = {name: sorted(places) for name, places in found.items() if name in FORBIDDEN | {"x-internal"}}
    assert leaks == {}
    assert {"eligibility", "balances", "risk_estimates_used"} <= set(found)


def test_the_walk_finds_the_internal_estimate_where_staff_may_see_it() -> None:
    spec = build_schema_app(create_app, __version__).openapi()
    agent = fields_of(spec, {"agent"})
    evaluator = fields_of(spec, {"evaluator"})
    assert {"band", "interval_low", "risk"} <= set(agent)
    assert {"probability", "band", "risk_estimates"} <= set(evaluator)
