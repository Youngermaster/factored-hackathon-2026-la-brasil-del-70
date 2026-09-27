"""Context checks shared by the PostgreSQL repositories (the same rules as the in-memory adapters)."""

from bank_agent.domain.access import AccessContext, Role
from bank_agent.domain.errors import AccessContextError
from bank_agent.domain.identifiers import CustomerId, StaffId


def customer_of(context: AccessContext) -> CustomerId:
    if context.role is not Role.CUSTOMER or context.customer_id is None:
        raise AccessContextError("this operation needs a customer context")
    return context.customer_id


def staff_of(context: AccessContext, role: Role) -> StaffId:
    if context.role is not role or context.staff_id is None:
        raise AccessContextError(f"this operation needs a {role.value} context")
    return context.staff_id
