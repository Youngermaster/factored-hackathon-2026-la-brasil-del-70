"""Customer repository port."""

from typing import Protocol

from bank_agent.domain.customer import Customer


class CustomerReader(Protocol):
    """Reads the customer of the bound context.

    Preconditions: bound to a customer ``AccessContext``.
    Postconditions: returns the context's own customer, never another.
    Errors: ``AccessContextError`` for a staff context; ``CustomerNotFoundError`` when the context names a
    customer that does not exist.
    Isolation: there is no way to ask for a different customer.
    """

    async def get_current(self) -> Customer:
        """Return the customer the context names."""
        ...


class CustomerRepository(CustomerReader, Protocol):
    """The full customer port. It adds no writes: customers are loaded by the seed, never by the workflow."""
