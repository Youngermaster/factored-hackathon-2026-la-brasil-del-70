"""Credit profile reader port."""

from typing import Protocol

from bank_agent.domain.credit import CreditProfile


class CreditProfileReader(Protocol):
    """Reads the bound customer's credit profile, derived from the core banking data.

    Preconditions: bound to a customer ``AccessContext``.
    Postconditions: returns the context customer's profile, or ``None`` when none exists. Missing facts stay
    ``None``; nothing is imputed.
    Errors: ``AccessContextError`` for an agent or evaluator context; staff never read credit profiles.
    Isolation: only the context customer's profile is reachable; the method takes no identifier. The score,
    income, days past due, and utilization are internal: never rendered to customers or sent to a model.
    """

    async def get_mine(self) -> CreditProfile | None:
        """Return the customer's credit profile, if one exists."""
        ...
