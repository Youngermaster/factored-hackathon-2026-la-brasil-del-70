"""No card, credit, eligibility, or application vocabulary can express an approval or a grant."""

import re
from enum import StrEnum

from pydantic import BaseModel

from bank_agent.domain import cards, credit, eligibility
from bank_agent.domain.actions import ActionKind, ToolName
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.transaction import TransactionStatus
from bank_agent.domain.workflow import Intent

FORBIDDEN = re.compile(r"approv|grant|pre_approv")
SCANNED_MODULES = (cards, credit, eligibility)
NEW_SHARED_MEMBERS = (
    ActionKind.SUBMIT_CREDIT_APPLICATION,
    *(member for member in ToolName if "credit" in member.value),
    EscalationReasonCode.CREDIT_REVIEW_REQUIRED,
    EscalationReasonCode.ELIGIBILITY_CONTESTED,
    EscalationReasonCode.CARD_UNBLOCK_REQUESTED,
    EscalationReasonCode.CARD_REPLACEMENT_REQUESTED,
    *(member for member in Intent if member.value.startswith(("credit", "card"))),
)


def _module_enums_and_models() -> tuple[list[type[StrEnum]], list[type[BaseModel]]]:
    enums: list[type[StrEnum]] = []
    models: list[type[BaseModel]] = []
    for module in SCANNED_MODULES:
        for value in vars(module).values():
            if isinstance(value, type) and value.__module__ == module.__name__:
                if issubclass(value, StrEnum):
                    enums.append(value)
                elif issubclass(value, BaseModel):
                    models.append(value)
    return enums, models


def test_scans_the_expected_vocabulary() -> None:
    enums, models = _module_enums_and_models()
    names = {enum.__name__ for enum in enums}
    assert {"CardAction", "CardBlockReason", "CreditProductType", "ApplicationStatus", "EligibilityOutcome"} <= names
    assert {"ReviewReason", "RiskBand", "UncertaintyFlag", "UncertaintyStatement", "ReviewPath"} <= names
    assert len(models) >= 10


def test_no_enum_member_means_approved_or_granted() -> None:
    enums, _ = _module_enums_and_models()
    offending = [
        f"{enum.__name__}.{member.value}" for enum in enums for member in enum if FORBIDDEN.search(member.value)
    ]
    offending += [member.value for member in NEW_SHARED_MEMBERS if FORBIDDEN.search(member.value)]
    assert offending == []


def test_no_field_name_means_approved_or_granted() -> None:
    _, models = _module_enums_and_models()
    offending = [
        f"{model.__name__}.{name}" for model in models for name in model.model_fields if FORBIDDEN.search(name)
    ]
    assert offending == []


def test_the_allowed_exception_is_outside_the_credit_vocabulary() -> None:
    """``approved`` is a card transaction status from the core banking data, not a credit outcome. The other
    exception, the scenario disclosure kind ``credit_approval_claim``, names the unsafe claim graders detect and
    is covered in ``evals/tests/unit/test_scenario_model_v1_1.py``."""
    assert TransactionStatus.APPROVED.value == "approved"
    assert TransactionStatus.__module__ not in {module.__name__ for module in SCANNED_MODULES}
