from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from bank_agent.ports.audit import AuditQuery
from bank_agent.ports.repositories.handoffs import HandoffQuery
from bank_agent.ports.repositories.transactions import MAX_TRANSACTION_PAGE, TransactionQuery
from bank_agent_builders import T0


def test_transaction_query_rejects_inverted_ranges_and_oversized_pages() -> None:
    with pytest.raises(ValidationError):
        TransactionQuery(occurred_from=T0, occurred_to=T0 - timedelta(days=1))
    with pytest.raises(ValidationError):
        TransactionQuery(min_amount=Decimal(10), max_amount=Decimal(5))
    with pytest.raises(ValidationError):
        TransactionQuery(limit=MAX_TRANSACTION_PAGE + 1)
    assert TransactionQuery(occurred_from=T0, occurred_to=T0).limit == 50


def test_query_limits_are_bounded() -> None:
    with pytest.raises(ValidationError):
        HandoffQuery(limit=0)
    with pytest.raises(ValidationError):
        AuditQuery(limit=501)
