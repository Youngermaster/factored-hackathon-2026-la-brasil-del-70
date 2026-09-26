import pytest
from pydantic import ValidationError

from bank_agent.domain.access import AccessContext, AuthLevel, Role
from bank_agent.domain.identifiers import CustomerId, StaffId


def test_auth_levels_are_ordered() -> None:
    assert AuthLevel.STEP_UP.satisfies(AuthLevel.OTP_VERIFIED)
    assert AuthLevel.OTP_VERIFIED.satisfies(AuthLevel.OTP_VERIFIED)
    assert not AuthLevel.IDENTIFIED.satisfies(AuthLevel.OTP_VERIFIED)
    assert not AuthLevel.NONE.satisfies(AuthLevel.IDENTIFIED)


def test_builds_customer_and_staff_contexts() -> None:
    customer = AccessContext.for_customer(CustomerId("C1"))
    assert customer.role is Role.CUSTOMER
    agent = AccessContext.for_staff(Role.AGENT, StaffId("agent-1"))
    assert agent.customer_id is None


@pytest.mark.parametrize(
    "fields",
    [
        {"role": "customer"},
        {"role": "customer", "customer_id": "C1", "staff_id": "agent-1"},
        {"role": "agent"},
        {"role": "evaluator", "staff_id": "ev-1", "customer_id": "C1"},
    ],
)
def test_rejects_inconsistent_subjects(fields: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        AccessContext.model_validate(fields)
