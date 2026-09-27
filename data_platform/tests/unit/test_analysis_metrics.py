import math

import pandas as pd
import pytest

from bank_data.analysis import metrics
from bank_data.analysis.config import CostAssumptions, CountryCost, LabeledFactor

INTERACTIONS = pd.DataFrame(
    {
        "was_resolved": [True, True, False, True, None],
        "was_escalated": [False, True, False, False, False],
        "requires_followup": [False, False, True, True, False],
        "duration_seconds": [120, 60, None, 300, 180],
        "country": ["MX", "CO", "MX", "AR", "BR"],
    }
)


def _costs() -> CostAssumptions:
    source = "fixture assumption for tests"
    return CostAssumptions(
        version=1,
        currency="USD",
        countries={
            "MX": CountryCost(loaded_cost_per_handled_minute=0.2, assumption=True, verified=False, source=source),
            "CO": CountryCost(loaded_cost_per_handled_minute=0.1, assumption=True, verified=False, source=source),
            "AR": CountryCost(loaded_cost_per_handled_minute=0.1, assumption=True, verified=False, source=source),
        },
        after_call_work_factor=LabeledFactor(value=1.5, assumption=True, verified=False, source=source),
        sensitivity_multipliers=(1.0,),
    )


def test_first_contact_resolution_ignores_unknown_outcomes() -> None:
    assert metrics.first_contact_resolution_rate(INTERACTIONS) == pytest.approx(3 / 4)


def test_escalation_rate_counts_escalated_contacts() -> None:
    assert metrics.escalation_rate(INTERACTIONS) == pytest.approx(1 / 5)


def test_simple_contact_rate_needs_resolved_unescalated_and_no_followup() -> None:
    # Rows 0 and 4 qualify on flags, but row 4 has an unknown resolution and is dropped: 1 of 4.
    assert metrics.simple_contact_rate(INTERACTIONS) == pytest.approx(1 / 4)


def test_rates_of_an_empty_frame_are_not_defined() -> None:
    empty = INTERACTIONS.iloc[0:0]
    assert metrics.first_contact_resolution_rate(empty) is None
    assert metrics.simple_contact_rate(empty) is None
    with pytest.raises(KeyError):
        metrics.escalation_rate(pd.DataFrame({"other": [1]}))


def test_sla_breach_rate_over_complaints() -> None:
    complaints = pd.DataFrame({"sla_breached": [True, False, False, True]})
    assert metrics.sla_breach_rate(complaints) == pytest.approx(0.5)


def test_handle_costs_use_country_rate_and_after_call_work() -> None:
    costs = metrics.handle_costs(INTERACTIONS, _costs())
    # 2 minutes * 0.2 * 1.5 = 0.6; 1 minute * 0.1 * 1.5 = 0.15; 5 minutes * 0.1 * 1.5 = 0.75.
    assert costs[0] == pytest.approx(0.6)
    assert costs[1] == pytest.approx(0.15)
    assert math.isnan(costs[2])  # unknown duration
    assert costs[3] == pytest.approx(0.75)
    assert math.isnan(costs[4])  # country without an assumption
    doubled = metrics.handle_costs(INTERACTIONS, _costs(), multiplier=2.0)
    assert doubled[0] == pytest.approx(1.2)


def test_cost_per_contact_and_per_resolved_contact() -> None:
    costs = metrics.handle_costs(INTERACTIONS, _costs())
    assert metrics.cost_per_contact(costs) == pytest.approx(1.5 / 3)
    total = metrics.estimated_total_cost(costs, contacts=5)
    assert total == pytest.approx(2.5)
    assert metrics.cost_per_resolved_contact(total, resolved=2) == pytest.approx(1.25)


def test_cost_per_resolved_contact_is_not_defined_without_resolutions() -> None:
    assert metrics.cost_per_resolved_contact(10.0, resolved=0) is None
    assert metrics.cost_per_resolved_contact(None, resolved=3) is None
    assert metrics.cost_per_contact(pd.Series([float("nan")])) is None
    assert metrics.estimated_total_cost(pd.Series([], dtype="float64"), contacts=4) is None
