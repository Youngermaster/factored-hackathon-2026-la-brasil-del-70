from datetime import timedelta

import pytest

from bank_agent.domain.errors import AccessContextError
from bank_agent_builders import T0
from bank_agent_contracts import AGENT, CONTEXT_A, CONTEXT_B, ReadBackend


class TestHistoricalComplaintReaderContract:
    async def test_lists_own_complaints_since_an_instant_newest_first(self, read_backend: ReadBackend) -> None:
        async with read_backend.readers(CONTEXT_A) as readers:
            recent = await readers.complaints.list_since(T0 - timedelta(days=90))
            count = await readers.complaints.count_since(T0 - timedelta(days=90))
            everything = await readers.complaints.count_since(T0 - timedelta(days=365))
        assert [item.complaint_id for item in recent] == ["CMP-A-0001", "CMP-A-0002"]
        assert (count, everything) == (2, 3)

    async def test_since_is_inclusive(self, read_backend: ReadBackend) -> None:
        async with read_backend.readers(CONTEXT_A) as readers:
            assert await readers.complaints.count_since(T0 - timedelta(days=10)) == 1

    async def test_never_counts_another_customers_complaints(self, read_backend: ReadBackend) -> None:
        async with read_backend.readers(CONTEXT_B) as readers:
            assert await readers.complaints.count_since(T0 - timedelta(days=365)) == 1

    async def test_staff_context_is_refused(self, read_backend: ReadBackend) -> None:
        async with read_backend.readers(AGENT) as readers:
            with pytest.raises(AccessContextError):
                await readers.complaints.count_since(T0)
