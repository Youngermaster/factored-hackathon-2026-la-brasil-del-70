import pytest

from bank_agent.domain.customer import Customer
from bank_agent.domain.errors import AccessContextError, CustomerNotFoundError
from bank_agent.domain.locale import Country
from bank_agent_contracts import AGENT, CONTEXT_A, CONTEXT_B, UNKNOWN_CUSTOMER, ReadBackend


class TestCustomerReaderContract:
    async def test_returns_the_context_customer_only(self, read_backend: ReadBackend) -> None:
        async with read_backend.readers(CONTEXT_A) as readers:
            customer = await readers.customers.get_current()
        assert isinstance(customer, Customer)
        assert customer.customer_id == CONTEXT_A.customer_id
        async with read_backend.readers(CONTEXT_B) as readers:
            assert (await readers.customers.get_current()).country is Country.CO

    async def test_unknown_customer_raises_not_found(self, read_backend: ReadBackend) -> None:
        async with read_backend.readers(UNKNOWN_CUSTOMER) as readers:
            with pytest.raises(CustomerNotFoundError):
                await readers.customers.get_current()

    async def test_staff_context_is_refused(self, read_backend: ReadBackend) -> None:
        async with read_backend.readers(AGENT) as readers:
            with pytest.raises(AccessContextError):
                await readers.customers.get_current()
