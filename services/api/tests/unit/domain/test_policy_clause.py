import pytest
from pydantic import ValidationError

from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.policy import ClauseFamily, ClauseMetadata, PolicyClause

FRONT_MATTER = {
    "clause_id": "DSP-CO-2.1",
    "version": 3,
    "jurisdiction": "CO",
    "language": "es",
    "effective_from": "2026-01-01",
    "synthetic": True,
    "params": {"dispute_window_days": 60, "auto_intake_max_amount": {"amount": "500", "currency": "USD"}},
    "bound_rules": ["DSP.within_window"],
    "summary": "Dispute window for card purchases.",
}


def test_parses_front_matter_with_money_params() -> None:
    metadata = ClauseMetadata.model_validate(FRONT_MATTER)
    assert metadata.family is ClauseFamily.DSP
    assert metadata.ref == ClauseRef.parse("DSP-CO-2.1@3")
    assert metadata.params["auto_intake_max_amount"] == Money.of("500", Currency.USD)
    clause = PolicyClause(metadata=metadata, body="Tienes {dispute_window_days} dias.")
    assert clause.ref == metadata.ref


@pytest.mark.parametrize(
    "overrides",
    [
        {"synthetic": False},
        {"jurisdiction": "MX"},
        {"params": {"auto_intake_max_amount_usd": 500.5}},
        {"clause_id": "FOO-CO-1"},
        {"bound_rules": ["not a rule"]},
        {"unexpected": 1},
    ],
)
def test_rejects_invalid_front_matter(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ClauseMetadata.model_validate({**FRONT_MATTER, **overrides})
