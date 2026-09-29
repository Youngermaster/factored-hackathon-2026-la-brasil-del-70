"""The customer's profile as the chat header shows it: their first name and their assistant profile (ADR 0025).

Reads run under the caller's session, so the customer is always the session's customer. Until the assistant
profile repository joins the unit of work (MVP track A, ``docs/plans/mvp-tuesday.md``), no profile can be saved,
so every customer sees the default profile, which is the documented profile of a customer who never changed it.
"""

from dataclasses import dataclass

from bank_agent.domain.access import Role
from bank_agent.domain.assistant_profile import AssistantProfile
from bank_agent.domain.errors import AccessContextError
from bank_agent.domain.session import Session
from bank_agent.ports.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True)
class CustomerProfile:
    first_name: str
    assistant: AssistantProfile


class ProfileService:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def current(self, session: Session) -> CustomerProfile:
        """The session customer's first name and assistant profile."""
        if session.role is not Role.CUSTOMER:
            raise AccessContextError("profiles belong to customer sessions")
        async with self._uow_factory(session.access_context()) as uow:
            customer = await uow.customers.get_current()
        return CustomerProfile(first_name=customer.first_name, assistant=AssistantProfile.default(customer.customer_id))
