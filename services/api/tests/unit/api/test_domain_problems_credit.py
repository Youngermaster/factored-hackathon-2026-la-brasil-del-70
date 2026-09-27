import pytest

from bank_agent.api.domain_problems import domain_problem_registry
from bank_agent.domain import errors
from bank_agent.domain.errors import DomainError


@pytest.mark.parametrize(
    ("error", "status", "slug", "code"),
    [
        (errors.CreditApplicationNotFoundError(), 404, "resource-not-found", "credit_application_not_found"),
        (
            errors.InvalidApplicationTransitionError(),
            409,
            "invalid-state-transition",
            "credit_application_transition_invalid",
        ),
        (errors.RiskEstimatorUnavailableError(), 503, "dependency-unavailable", "risk_estimator_unavailable"),
        (
            errors.EligibilityServiceUnavailableError(),
            503,
            "dependency-unavailable",
            "eligibility_service_unavailable",
        ),
    ],
)
def test_credit_errors_map_to_their_family_problem(error: DomainError, status: int, slug: str, code: str) -> None:
    problem = domain_problem_registry().problem_for(error)
    assert problem is not None
    assert (problem.status, problem.slug) == (status, slug)
    assert error.code == code


def test_the_risk_estimator_is_never_retried() -> None:
    assert errors.RiskEstimatorUnavailableError.retryable is False
