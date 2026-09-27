"""The synthetic eligibility service and its customer-facing renderer."""

from bank_agent.policy.eligibility.render import render_eligibility
from bank_agent.policy.eligibility.service import SyntheticEligibilityService, map_outcome

__all__ = ["SyntheticEligibilityService", "map_outcome", "render_eligibility"]
