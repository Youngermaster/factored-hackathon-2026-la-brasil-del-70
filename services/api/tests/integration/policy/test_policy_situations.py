"""The YAML table of representative situations, evaluated against the real pack and catalog."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from bank_agent.adapters.policy.filesystem import FilesystemCreditCatalog, FilesystemPolicyRepository
from bank_agent.bootstrap.settings import DEFAULT_DATA_AS_OF, DEFAULT_POLICY_DIR
from bank_agent.domain.access import AuthLevel
from bank_agent.domain.actions import ActionKind
from bank_agent.domain.credit import CreditProfile
from bank_agent.domain.decision import DecisionKind
from bank_agent.domain.eligibility import EligibilityOutcome, RiskBand, UncertaintyFlag
from bank_agent.domain.identifiers import CreditProductCode
from bank_agent.domain.locale import Country
from bank_agent.domain.money import Money
from bank_agent.domain.session import SessionSnapshot
from bank_agent.domain.trust import TrustEventKind, TrustState
from bank_agent.domain.workflow import WorkflowId
from bank_agent.policy.eligibility import SyntheticEligibilityService
from bank_agent.policy.evaluator import evaluate
from bank_agent.policy.facts import EvaluationRequest, PolicyFacts
from bank_agent.ports.eligibility import CreditApplicationFacts, EligibilityRequest
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.ids import SequentialIdGenerator
from bank_agent_builders import CUSTOMER_A, T0, risk_estimate
from bank_agent_policy import action, snapshot, trust

TABLE = yaml.safe_load((Path(__file__).parent / "policy_situations.yaml").read_text(encoding="utf-8"))
REPOSITORY = FilesystemPolicyRepository.from_directory(DEFAULT_POLICY_DIR)
PACK = REPOSITORY.pack
CATALOG = FilesystemCreditCatalog.from_directory(DEFAULT_POLICY_DIR, PACK)
SESSIONS: dict[str, SessionSnapshot | None] = {
    "none": None,
    "identified": snapshot(AuthLevel.IDENTIFIED),
    "otp": snapshot(),
    "step_up": snapshot(step_up=True),
    "expired": snapshot(expired=True),
}
TRUST: dict[str, TrustState | None] = {
    "low": None,
    "elevated": trust(TrustEventKind.INJECTION_DETECTED),
    "high": trust(TrustEventKind.CROSS_CUSTOMER_PROBE),
}


def _facts(row: dict[str, Any]) -> PolicyFacts:
    raw = dict(row.get("facts", {}))
    credit = raw.get("credit")
    if credit is not None and "product_code" in credit:
        code = credit.pop("product_code")
        credit = {**credit, "requested_product_code": code, "product": CATALOG.get(CreditProductCode(code))}
        raw["credit"] = credit
    return PolicyFacts.model_validate({**raw, "jurisdiction": row["country"], "data_as_of": DEFAULT_DATA_AS_OF})


def _request(row: dict[str, Any]) -> EvaluationRequest:
    spec = row.get("action")
    act = action(ActionKind(spec["kind"]), row["state"], confirmed=spec["confirmed"]) if spec else None
    return EvaluationRequest(
        workflow=WorkflowId(row["workflow"]),
        state=row["state"],
        action=act,
        session=SESSIONS[row.get("session", "otp")],
        trust=TRUST[row.get("trust", "low")],
        facts=_facts(row),
    )


def test_the_table_covers_every_workflow_jurisdiction_and_path() -> None:
    kinds = {"allow", "require_confirmation"}
    for workflow in WorkflowId:
        for country in Country:
            rows = [r for r in TABLE["decisions"] if r["workflow"] == workflow.value and r["country"] == country.value]
            assert any(r["expect"] in kinds for r in rows), (workflow, country, "normal")
            assert any("unsupported" in r["id"] for r in rows), (workflow, country, "unsupported")
            assert any(r["expect"] == "escalate" for r in rows), (workflow, country, "escalation")


@pytest.mark.parametrize("row", TABLE["decisions"], ids=lambda row: row["id"])
def test_decision_situation(row: dict[str, Any]) -> None:
    decision = evaluate(_request(row), PACK)
    assert decision.kind is DecisionKind(row["expect"]), [
        (r.rule_id, r.reason_code) for r in decision.rule_results if not r.passed
    ]
    if "decisive" in row:
        assert list(decision.decisive_rule_ids) == row["decisive"]
    assert decision.policy_pack_version == PACK.version


def _profile(spec: dict[str, Any] | None, currency: str) -> CreditProfile | None:
    if spec is None:
        return None
    income = spec.get("income")
    return CreditProfile(
        customer_id=CUSTOMER_A,
        credit_score=spec["credit_score"],
        estimated_monthly_income=Money.model_validate({"amount": income, "currency": currency}) if income else None,
        tenure_months=spec["tenure_months"],
        max_days_past_due=spec["max_days_past_due"],
        as_of=date(2026, 6, 17),
    )


def _estimate(spec: dict[str, Any] | None) -> Any:
    if spec is None:
        return None
    low, high = Decimal(spec["low"]), Decimal(spec["high"])
    band = RiskBand(spec["band"])
    flags = [UncertaintyFlag.MISSING_FEATURES] if band is RiskBand.UNKNOWN else []
    return risk_estimate(probability=(low + high) / 2, interval_low=low, interval_high=high, band=band, flags=flags)


@pytest.mark.parametrize("row", TABLE["eligibility"], ids=lambda row: row["id"])
def test_eligibility_situation(row: dict[str, Any]) -> None:
    product = CATALOG.get(CreditProductCode(row["product"]))
    assert product is not None
    request = EligibilityRequest(
        product=product,
        profile=_profile(row["profile"], product.currency.value),
        application=CreditApplicationFacts(
            requested_amount=Money.model_validate({"amount": row["amount"], "currency": product.currency.value}),
            requested_term_months=row["term"],
            purpose="general_purpose" if product.product_type.value != "mortgage" else "home_purchase",
        ),
        risk_estimate=_estimate(row["estimate"]),
        jurisdiction=product.jurisdiction,
        as_of=datetime(2026, 9, 27, tzinfo=UTC),
    )
    assessment = SyntheticEligibilityService(PACK, FixedClock(T0), SequentialIdGenerator()).assess(request)
    assert assessment.outcome is EligibilityOutcome(row["expect"]), [
        (r.rule_id, r.reason_code) for r in assessment.rule_results if not r.passed
    ]
    assert [reason.value for reason in assessment.review_reasons] == row.get("reasons", [])
    assert all(result.clause_refs for result in assessment.rule_results)
