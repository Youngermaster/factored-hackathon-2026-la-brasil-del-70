import pytest

from bank_agent.domain.access import AccessContext
from bank_agent.domain.credit import CreditProfile
from bank_agent.domain.errors import AccessContextError
from bank_agent_contracts import AGENT, CONTEXT_A, CONTEXT_B, EVALUATOR, UNKNOWN_CUSTOMER, ReadBackend


class TestCreditProfileReaderContract:
    async def test_returns_the_customers_own_profile(self, read_backend: ReadBackend) -> None:
        async with read_backend.readers(CONTEXT_A) as readers:
            profile = await readers.credit_profiles.get_mine()
        assert isinstance(profile, CreditProfile)
        assert profile.customer_id == "CUS-A-0001"
        assert profile.credit_score == 712
        assert profile.missing_facts() == ()

    async def test_missing_facts_stay_missing(self, read_backend: ReadBackend) -> None:
        async with read_backend.readers(CONTEXT_B) as readers:
            profile = await readers.credit_profiles.get_mine()
        assert profile is not None
        assert profile.customer_id == "CUS-B-0002"
        assert profile.estimated_monthly_income is None
        assert profile.missing_facts() == ("estimated_monthly_income",)

    async def test_a_customer_without_a_profile_gets_none(self, read_backend: ReadBackend) -> None:
        async with read_backend.readers(UNKNOWN_CUSTOMER) as readers:
            assert await readers.credit_profiles.get_mine() is None

    @pytest.mark.parametrize("staff", [AGENT, EVALUATOR], ids=["agent", "evaluator"])
    async def test_staff_never_read_credit_profiles(self, read_backend: ReadBackend, staff: AccessContext) -> None:
        async with read_backend.readers(staff) as readers:
            with pytest.raises(AccessContextError):
                await readers.credit_profiles.get_mine()
