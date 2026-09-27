"""Builders for policy kernel tests: sessions, facts, rule contexts, and a small in-memory fixture pack.

Every value is synthetic and labeled as a fixture. The fixture pack is built in memory (no files), with one
clause per rule group and the same parameter names as the real pack, so unit tests exercise the kernel alone.
"""

from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

from bank_agent.domain.access import AuthLevel, Role
from bank_agent.domain.actions import (
    ActionKind,
    ActionRequest,
    BlockCardArguments,
    CreateDisputeArguments,
    SubmitCreditApplicationArguments,
)
from bank_agent.domain.decision import ParamValue
from bank_agent.domain.dispute import DisputeReason
from bank_agent.domain.eligibility import EligibilityOutcome, ReviewPath, UncertaintyStatement
from bank_agent.domain.identifiers import (
    CreditProductCode,
    IdempotencyKey,
    LineageId,
    ProductId,
    SourceRef,
    SourceTable,
    TransactionId,
)
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.policy import ActionRequirement, ClauseMetadata, Jurisdiction, PolicyClause
from bank_agent.domain.session import SessionSnapshot
from bank_agent.domain.transaction import TransactionStatus
from bank_agent.domain.trust import TrustEvent, TrustEventKind, TrustState
from bank_agent.domain.workflow import Intent, WorkflowId
from bank_agent.policy.facts import EvaluationRequest, PolicyFacts, TransactionFacts
from bank_agent.policy.pack import Bindings, PackInfo, PolicyPack, StateBinding
from bank_agent.policy.rules import CONVERSATION_RULES, ELIGIBILITY_RULES, RuleContext

NOW = datetime(2026, 9, 27, 15, 0, tzinfo=UTC)
DATA_AS_OF = date(2026, 6, 17)
CUSTOMER = "CUS-A-0001"


def snapshot(
    level: AuthLevel = AuthLevel.OTP_VERIFIED,
    *,
    step_up: bool = False,
    expired: bool = False,
    role: Role = Role.CUSTOMER,
) -> SessionSnapshot:
    subject: dict[str, Any] = {"customer_id": CUSTOMER} if role is Role.CUSTOMER else {"staff_id": "STF-0001"}
    effective = AuthLevel.NONE if expired else (AuthLevel.STEP_UP if step_up else level)
    return SessionSnapshot(
        role=role,
        effective_auth_level=effective,
        step_up_valid=step_up and not expired,
        expired=expired,
        at=NOW,
        **subject,
    )


def trust(*kinds: TrustEventKind) -> TrustState:
    events = tuple(
        TrustEvent(kind=kind, occurred_at=NOW, detector="fixture:detector@1", detail_code="fixture") for kind in kinds
    )
    return TrustState(lineage_id=LineageId("lin-fixture-0001"), events=events)


def facts(country: Country = Country.MX, **overrides: Any) -> PolicyFacts:
    fields: dict[str, Any] = {"jurisdiction": country, "data_as_of": DATA_AS_OF}
    return PolicyFacts.model_validate({**fields, **overrides})


def transaction_facts(**overrides: Any) -> TransactionFacts:
    fields: dict[str, Any] = {
        "owned_by_session_customer": True,
        "status": TransactionStatus.APPROVED,
        "occurred_on": date(2026, 6, 1),
        "amount": Money.of("1500.00", Currency.MXN),
    }
    return TransactionFacts.model_validate({**fields, **overrides})


def action(kind: ActionKind, state: str, *, confirmed: bool = False) -> ActionRequest:
    arguments: Any
    if kind is ActionKind.BLOCK_CARD:
        arguments, target = (
            BlockCardArguments(product_id=ProductId("PRD-0001")),
            SourceRef.of(SourceTable.PRODUCTS, "PRD-0001"),
        )
    elif kind is ActionKind.CREATE_DISPUTE_CASE:
        amount = Money.of("1500.00", Currency.MXN)
        arguments = CreateDisputeArguments(
            transaction_id=TransactionId("TXN-0001"), reason=DisputeReason.UNRECOGNIZED, disputed_amount=amount
        )
        target = SourceRef.of(SourceTable.TRANSACTIONS, "TXN-0001")
    else:
        arguments = SubmitCreditApplicationArguments(
            product_code=CreditProductCode("MX-PL-STANDARD"),
            requested_amount=Money.of("60000.00", Currency.MXN),
            requested_term_months=24,
            purpose="general_purpose",
        )
        target = SourceRef.of(SourceTable.CREDIT_APPLICATIONS, "app-fixture-0001")
    return ActionRequest(
        action=kind,
        target=target,
        arguments=arguments,
        idempotency_key=IdempotencyKey("idem-fixture-0001"),
        requested_in_state=state,
        confirmed_at=NOW if confirmed else None,
    )


def request(
    workflow: WorkflowId = WorkflowId.DISPUTE,
    state: str = "COLLECT_DETAILS",
    *,
    facts_: PolicyFacts | None = None,
    session: SessionSnapshot | None = None,
    action_: ActionRequest | None = None,
    trust_: TrustState | None = None,
) -> EvaluationRequest:
    return EvaluationRequest(
        workflow=workflow,
        state=state,
        action=action_,
        session=session if session is not None else snapshot(),
        trust=trust_,
        facts=facts_ if facts_ is not None else facts(intent=Intent.DISPUTE_NEW),
    )


def context(
    params: Mapping[str, Any] | None = None,
    *,
    request_: EvaluationRequest | None = None,
    state_auth: AuthLevel = AuthLevel.OTP_VERIFIED,
    requirement: ActionRequirement | None = None,
) -> RuleContext:
    return RuleContext(
        request=request_ if request_ is not None else request(),
        params=params or {},
        state_auth=state_auth,
        requirement=requirement,
    )


def clause(
    clause_id: str,
    *,
    params: dict[str, Any] | None = None,
    rules: tuple[str, ...] = (),
    body: str = "Fixture clause text.",
    language: Language = Language.ES,
    version: int = 1,
) -> PolicyClause:
    metadata = ClauseMetadata(
        clause_id=clause_id,
        version=version,
        jurisdiction=Jurisdiction(clause_id.split("-")[1]),
        language=language,
        effective_from=date(2026, 9, 27),
        synthetic=True,
        params=params or {},
        bound_rules=rules,
        summary="Fixture clause.",
    )
    return PolicyClause(metadata=metadata, body=body)


_ALL_WORKFLOWS = ["account_inquiry", "card_support", "dispute", "credit"]
_REASONS = [
    "unrecognized",
    "duplicate",
    "wrong_amount",
    "not_received",
    "atm_cash_not_dispensed",
    "subscription_cancelled",
]


def _family(prefix: str) -> tuple[str, ...]:
    return tuple(rule_id for rule_id in CONVERSATION_RULES.order() if rule_id.startswith(prefix))


_ESC_CREDIT = ("ESC.credit_review_required", "ESC.eligibility_contested")
_ESC_COMMON = tuple(rule_id for rule_id in _family("ESC.") if rule_id not in _ESC_CREDIT)
_ELG_PRODUCT_RULES = (
    "ELG.credit_score_minimum",
    "ELG.payment_to_income_max",
    "ELG.days_past_due_max",
    "ELG.tenure_minimum",
    "ELG.amount_within_product_range",
    "ELG.risk_band_acceptable",
)


def _elg_product(kind: str, **extra: ParamValue) -> dict[str, Any]:
    return {
        "product_type": kind,
        "min_credit_score": 650,
        "max_payment_to_income_pct": 35,
        "max_days_past_due": 0,
        "min_tenure_months": 12,
        "acceptable_risk_bands": ["low", "medium"],
        "review_amount_threshold": Money.of("200000.00", Currency.MXN),
        **extra,
    }


FIXTURE_CLAUSES: dict[str, tuple[dict[str, Any], tuple[str, ...]]] = {
    "SCOPE-ALL-1": (
        {"supported_workflows": _ALL_WORKFLOWS},
        ("SCOPE.workflow_supported", "SCOPE.supported_intent", "SCOPE.action_allowed_in_state"),
    ),
    "AUTH-ALL-1": (
        {"step_up_window_minutes": 5, "elevated_risk_required_level": "step_up"},
        ("AUTH.session_valid", "AUTH.required_level", "AUTH.step_up_valid"),
    ),
    "PRV-ALL-1": ({}, ("PRV.no_cross_customer_access", "PRV.no_third_party_disclosure")),
    "ESC-ALL-1": (
        {
            "repeat_complaint_threshold": 3,
            "repeat_complaint_lookback_days": 180,
            "clarification_budget": 2,
            "tool_retry_budget": 2,
        },
        _ESC_COMMON,
    ),
    "ESC-ALL-4": ({}, _ESC_CREDIT),
    "ACC-ALL-1": ({"max_statement_days": 92}, _family("ACC.")),
    "CRD-ALL-1": ({"block_requires_step_up": True}, _family("CRD.")),
    "DSP-MX-1": ({"dispute_window_days": 90}, ("DSP.within_window",)),
    "DSP-MX-3": ({"auto_intake_max_amount": Money.of("10000.00", Currency.MXN)}, ("DSP.amount_within_auto_limit",)),
    "DSP-ALL-1": (
        {
            "eligible_statuses": ["approved"],
            "required_fields": ["transaction", "reason", "disputed_amount"],
            "supported_reasons": _REASONS,
        },
        (
            "DSP.transaction_owned_by_session_customer",
            "DSP.status_eligible",
            "DSP.not_already_disputed",
            "DSP.reason_supported",
            "DSP.required_fields_present",
            "DSP.case_within_sla",
        ),
    ),
    "CRE-ALL-1": ({}, _family("CRE.")),
    "ELG-ALL-1": ({}, ("ELG.credit_score_present", "ELG.income_present")),
    "ELG-ALL-2": (
        {"risk_cut_medium_bps": 2000, "risk_cut_high_bps": 3500, "borderline_margin_bps": 100},
        ("ELG.risk_estimate_available", "ELG.risk_interval_not_borderline"),
    ),
    "ELG-ALL-3": ({}, ("ELG.self_service_product",)),
    "ELG-MX-1.1": (_elg_product("credit_card", card_payment_pct_of_limit=5), _ELG_PRODUCT_RULES),
    "ELG-MX-1.2": (_elg_product("personal_loan"), _ELG_PRODUCT_RULES),
}


def _state(auth: AuthLevel, *clauses: str) -> StateBinding:
    return StateBinding(auth=auth, clauses=clauses)


OTP = AuthLevel.OTP_VERIFIED
FIXTURE_BINDINGS = Bindings(
    common=("SCOPE-ALL-1", "AUTH-ALL-1", "PRV-ALL-1", "ESC-ALL-1"),
    workflows={
        WorkflowId.ACCOUNT_INQUIRY: {
            "START": _state(AuthLevel.NONE, "SCOPE-ALL-1"),
            "ANSWER_STATEMENT": _state(OTP, "ACC-ALL-1"),
        },
        WorkflowId.CARD_SUPPORT: {
            "START": _state(AuthLevel.NONE, "SCOPE-ALL-1"),
            "IDENTIFY_CARD": _state(OTP, "CRD-ALL-1"),
            "CONFIRM_BLOCK": _state(OTP, "CRD-ALL-1"),
            "EXECUTE_BLOCK": _state(OTP, "CRD-ALL-1"),
        },
        WorkflowId.DISPUTE: {
            "START": _state(AuthLevel.NONE, "SCOPE-ALL-1"),
            "COLLECT_DETAILS": _state(OTP, "DSP-ALL-1", "DSP-{country}-1", "DSP-{country}-3"),
            "CREATE_CASE": _state(OTP, "DSP-ALL-1", "DSP-{country}-1", "DSP-{country}-3"),
            "EXECUTE_BLOCK": _state(OTP, "CRD-ALL-1"),
        },
        WorkflowId.CREDIT: {
            "START": _state(AuthLevel.NONE, "SCOPE-ALL-1"),
            "PRODUCT_DETAIL": _state(OTP, "CRE-ALL-1"),
            "PRESENT_ELIGIBILITY": _state(OTP, "CRE-ALL-1", "ESC-ALL-4", "ELG-ALL-1"),
            "SUBMIT_APPLICATION": _state(OTP, "CRE-ALL-1"),
        },
    },
)


def _requirement(kind: ActionKind, states: dict[WorkflowId, tuple[str, ...]]) -> ActionRequirement:
    return ActionRequirement(
        action=kind,
        requires_confirmation=True,
        required_auth_level=OTP,
        requires_step_up=True,
        allowed_states=states,
    )


FIXTURE_MATRIX = {
    ActionKind.CREATE_DISPUTE_CASE: _requirement(
        ActionKind.CREATE_DISPUTE_CASE, {WorkflowId.DISPUTE: ("CREATE_CASE",)}
    ),
    ActionKind.BLOCK_CARD: _requirement(
        ActionKind.BLOCK_CARD,
        {WorkflowId.CARD_SUPPORT: ("CONFIRM_BLOCK", "EXECUTE_BLOCK"), WorkflowId.DISPUTE: ("EXECUTE_BLOCK",)},
    ),
    ActionKind.SUBMIT_CREDIT_APPLICATION: _requirement(
        ActionKind.SUBMIT_CREDIT_APPLICATION, {WorkflowId.CREDIT: ("SUBMIT_APPLICATION",)}
    ),
}


def fixture_messages(language: Language) -> dict[str, dict[str, str]]:
    tag = f"[fixture {language.value}]"
    specs = ELIGIBILITY_RULES.specs()
    return {
        "heading": {key: f"{tag} {key}" for key in ("reasons", "missing", "synthetic_notice")},
        "outcome": {outcome.value: f"{tag} outcome {outcome.value}" for outcome in EligibilityOutcome},
        "reason": {code: f"{tag} reason {code}" for spec in specs for code in spec.reason_codes},
        "missing_fact": {fact: f"{tag} missing {fact}" for spec in specs for fact in spec.missing_facts},
        "uncertainty": {item.value: f"{tag} uncertainty {item.value}" for item in UncertaintyStatement},
        "review_path": {item.value: f"{tag} review {item.value}" for item in ReviewPath},
    }


def fixture_pack(version: str = "pack-fixture-0001") -> PolicyPack:
    """A small, valid-by-construction pack. It is built directly, without the loader."""
    clauses = {
        (clause_id, language): [
            clause(
                clause_id, params=params, rules=rules, language=language, body=f"[fixture {language.value}] {clause_id}"
            )
        ]
        for clause_id, (params, rules) in FIXTURE_CLAUSES.items()
        for language in Language
    }
    return PolicyPack(
        version=version,
        info=PackInfo(
            pack_id="fixture-pack",
            label="Fixture pack",
            synthetic=True,
            supported_workflows=tuple(WorkflowId),
            languages=tuple(Language),
        ),
        clauses=clauses,
        bindings=FIXTURE_BINDINGS,
        matrix=FIXTURE_MATRIX,
        messages={language: fixture_messages(language) for language in Language},
    )
