import pytest

from bank_data.errors import SeedVerificationError
from bank_data.seed.verify import _assert_same


def test_reconciliation_reports_counts_not_customer_ids() -> None:
    with pytest.raises(SeedVerificationError) as raised:
        _assert_same("customers", {"private-customer-id"}, {"different-private-id"})
    message = str(raised.value)
    assert "1 missing, 1 extra" in message
    assert "private-customer-id" not in message
    assert "different-private-id" not in message
