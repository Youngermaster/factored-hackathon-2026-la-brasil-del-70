"""Operational metrics over contact-center and complaint frames.

Rates are computed over non-null values; a frame without usable rows yields ``None`` (reported as "not
defined"), never zero.
"""

import pandas as pd

from bank_data.analysis.config import CostAssumptions


def _rate(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame.columns:
        raise KeyError(column)
    values = frame[column].dropna()
    if values.empty:
        return None
    return float(values.astype(bool).mean())


def first_contact_resolution_rate(interactions: pd.DataFrame) -> float | None:
    """Share of interactions resolved at first contact (``was_resolved``)."""
    return _rate(interactions, "was_resolved")


def escalation_rate(interactions: pd.DataFrame) -> float | None:
    """Share of interactions escalated to a supervisor (``was_escalated``)."""
    return _rate(interactions, "was_escalated")


def simple_contact_rate(interactions: pd.DataFrame) -> float | None:
    """The pre-registered automatable-share proxy: resolved at first contact, not escalated, and no follow-up."""
    usable = interactions.dropna(subset=["was_resolved", "was_escalated", "requires_followup"])
    if usable.empty:
        return None
    simple = (
        usable["was_resolved"].astype(bool)
        & ~usable["was_escalated"].astype(bool)
        & ~usable["requires_followup"].astype(bool)
    )
    return float(simple.mean())


def sla_breach_rate(complaints: pd.DataFrame) -> float | None:
    """Share of complaints whose SLA was breached (``sla_breached``; a post-outcome field)."""
    return _rate(complaints, "sla_breached")


def handle_costs(interactions: pd.DataFrame, costs: CostAssumptions, *, multiplier: float = 1.0) -> pd.Series:
    """Assumed cost of each interaction: handled minutes times the loaded cost per minute of the customer's
    country, times the after-call-work factor and the sensitivity ``multiplier``. NaN when the duration or
    the country's cost is unknown."""
    per_minute = interactions["country"].map(
        lambda code: costs.cost_per_minute(code if isinstance(code, str) else None)
    )
    minutes = interactions["duration_seconds"].astype("float64") / 60.0
    return minutes * per_minute.astype("float64") * multiplier


def cost_per_contact(costs: pd.Series) -> float | None:
    """Mean assumed cost over the contacts whose cost is known."""
    known = costs.dropna()
    return None if known.empty else float(known.mean())


def cost_per_resolved_contact(total_cost: float | None, resolved: int) -> float | None:
    """Total assumed cost divided by resolved contacts; ``None`` ("not defined") without resolutions."""
    if total_cost is None or resolved <= 0:
        return None
    return total_cost / resolved


def estimated_total_cost(costs: pd.Series, contacts: int) -> float | None:
    """Mean known cost times all contacts: contacts without a duration are costed at the mean."""
    mean = cost_per_contact(costs)
    return None if mean is None else mean * contacts
