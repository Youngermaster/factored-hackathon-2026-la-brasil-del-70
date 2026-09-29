"""The domain error taxonomy.

Every error has a stable, machine-readable ``code`` (snake case, unique across the taxonomy) and a
``retryable`` flag. Messages never contain personal data or input values. The HTTP layer maps error families
to RFC 9457 problem types in one place (``bank_agent.api.domain_problems``); nothing else formats errors.

Model construction failures (a handoff without a source reference, a float amount) surface as Pydantic
``ValidationError``, because validators raise ``ValueError``. The classes below cover failures of behavior:
arithmetic across currencies, illegal lifecycle moves, access, conflicts, and dependency failures that port
implementations raise.
"""

from datetime import timedelta
from typing import ClassVar, Literal


class DomainError(Exception):
    """Base class for every domain error."""

    code: ClassVar[str] = "domain_error"
    retryable: ClassVar[bool] = False

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code.replace("_", " "))


# --- Invariant violations ------------------------------------------------------------------------------------


class InvariantViolationError(DomainError):
    """An operation would break an invariant of a value object or entity."""

    code = "invariant_violation"


class ToolArgumentError(InvariantViolationError):
    """A tool argument is outside what the tool accepts (for example a statement period that is too long)."""

    code = "tool_argument_invalid"


class CurrencyMismatchError(InvariantViolationError):
    code = "currency_mismatch"


class ExchangeRateMismatchError(InvariantViolationError):
    code = "exchange_rate_mismatch"


class MoneyPrecisionError(InvariantViolationError):
    """The exact result of a money operation does not fit the decimal context."""

    code = "money_precision_exceeded"


class InvalidMaskedNumberError(InvariantViolationError):
    code = "masked_number_invalid"


class TrustStateViolationError(InvariantViolationError):
    """An attempt to rewrite, reorder, or mix risk evidence."""

    code = "trust_state_append_only"


class ClockRegressionError(InvariantViolationError):
    code = "clock_regression"


# --- State transitions ---------------------------------------------------------------------------------------


class StateTransitionError(DomainError):
    code = "state_transition_invalid"


class InvalidCaseTransitionError(StateTransitionError):
    code = "case_transition_invalid"


class InvalidProductStateError(StateTransitionError):
    code = "product_state_invalid"


class InvalidHandoffTransitionError(StateTransitionError):
    code = "handoff_transition_invalid"


class InvalidApplicationTransitionError(StateTransitionError):
    code = "credit_application_transition_invalid"


class WorkflowTransitionError(StateTransitionError):
    """A workflow definition does not allow the move between two of its states, or names an unknown state."""

    code = "workflow_transition_invalid"


# --- Not found -----------------------------------------------------------------------------------------------


class NotFoundError(DomainError):
    """The resource does not exist, or belongs to another customer. Both cases are indistinguishable."""

    code = "not_found"


class CustomerNotFoundError(NotFoundError):
    code = "customer_not_found"


class ProductNotFoundError(NotFoundError):
    code = "product_not_found"


class TransactionNotFoundError(NotFoundError):
    code = "transaction_not_found"


class CaseNotFoundError(NotFoundError):
    code = "case_not_found"


class ConversationNotFoundError(NotFoundError):
    code = "conversation_not_found"


class HandoffNotFoundError(NotFoundError):
    code = "handoff_not_found"


class CreditApplicationNotFoundError(NotFoundError):
    code = "credit_application_not_found"


class SessionNotFoundError(NotFoundError):
    code = "session_not_found"


# --- Authentication ------------------------------------------------------------------------------------------


class AuthenticationError(DomainError):
    code = "authentication_required"


class SessionExpiredError(AuthenticationError):
    code = "session_expired"

    def __init__(self, reason: Literal["idle", "absolute"]) -> None:
        super().__init__(f"session expired ({reason})")
        self.reason = reason


class SessionRevokedError(AuthenticationError):
    code = "session_revoked"


class IdentityChallengeFailedError(AuthenticationError):
    """Deliberately generic: covers an unknown customer and a wrong code alike."""

    code = "identity_challenge_failed"


class IdentityChallengeExpiredError(AuthenticationError):
    code = "identity_challenge_expired"


class IdentityLockedError(AuthenticationError):
    code = "identity_locked"

    def __init__(self, retry_after: timedelta) -> None:
        super().__init__("identity verification is temporarily locked")
        self.retry_after = retry_after


# --- Authorization -------------------------------------------------------------------------------------------


class AuthorizationError(DomainError):
    code = "authorization_failed"


class InsufficientAuthLevelError(AuthorizationError):
    code = "auth_level_insufficient"


class StepUpRequiredError(AuthorizationError):
    code = "step_up_required"


class ToolNotAllowedError(AuthorizationError):
    """The current workflow state's allowlist does not include the tool; the engine refuses the call."""

    code = "tool_not_allowed"


class AccessContextError(AuthorizationError):
    """A repository was used with a role it does not serve. This is a programming error, never user-facing."""

    code = "access_context_invalid"


# --- Conflicts -----------------------------------------------------------------------------------------------


class ConflictError(DomainError):
    code = "conflict"


class ConcurrencyConflictError(ConflictError):
    code = "concurrency_conflict"


class IdempotencyConflictError(ConflictError):
    """The idempotency key was already used for a different request."""

    code = "idempotency_key_conflict"


class AppendOnlyViolationError(ConflictError):
    code = "append_only_violation"


class DuplicateEntityError(ConflictError):
    code = "duplicate_entity"


class TurnConflictError(ConflictError):
    """A client turn id that was already used in another conversation."""

    code = "turn_conflict"


# --- Dependencies --------------------------------------------------------------------------------------------


class DependencyError(DomainError):
    code = "dependency_failure"


class LlmError(DependencyError):
    code = "llm_error"


class LlmTimeoutError(LlmError):
    code = "llm_timeout"
    retryable = True


class LlmRateLimitedError(LlmError):
    code = "llm_rate_limited"
    retryable = True


class LlmProviderError(LlmError):
    code = "llm_provider_error"
    retryable = True


class LlmProviderRejectedError(LlmProviderError):
    """The provider refused the request (authentication, a malformed request, an unknown model) or no provider
    is configured. A provider error, but never retried: the same request fails the same way."""

    code = "llm_provider_rejected"
    retryable = False


class LlmInvalidOutputError(LlmError):
    code = "llm_invalid_output"


class LlmBudgetExceededError(LlmError):
    code = "llm_budget_exceeded"


class LlmCircuitOpenError(LlmError):
    code = "llm_circuit_open"


class ToolError(DependencyError):
    code = "tool_error"


class ToolTimeoutError(ToolError):
    code = "tool_timeout"
    retryable = True


class ToolTransientError(ToolError):
    code = "tool_transient_failure"
    retryable = True


class ToolPermanentError(ToolError):
    code = "tool_permanent_failure"


class DatabaseUnavailableError(DependencyError):
    """The database refused or dropped the connection, timed out, or is read-only (degradation level L4).

    The request's unit of work was rolled back, so nothing it tried to write was committed by it; the API answers 503
    with ``Retry-After``. Writes never fail open: a write whose outcome is unknown is not reported as done.
    """

    code = "database_unavailable"
    retryable = True


class RiskEstimatorUnavailableError(DependencyError):
    """The risk estimator cannot produce an estimate. Never retried: the eligibility service falls back to
    human review instead of guessing."""

    code = "risk_estimator_unavailable"


class EligibilityServiceUnavailableError(DependencyError):
    code = "eligibility_service_unavailable"


class ModelArtifactNotFoundError(DependencyError):
    code = "model_artifact_not_found"


class ModelArtifactIntegrityError(DependencyError):
    code = "model_artifact_integrity"


class ModelUnavailableError(DependencyError):
    """A registered model cannot serve in this process (for example its optional extra is not installed)."""

    code = "model_unavailable"


# --- Configuration -------------------------------------------------------------------------------------------


class ConfigurationError(DomainError):
    code = "configuration_error"


class WorkflowRegistryError(ConfigurationError):
    """The workflow registry is incomplete or inconsistent with the catalog, bindings, matrix, or tools."""

    code = "workflow_registry_invalid"


class PromptNotFoundError(ConfigurationError):
    code = "prompt_not_found"


class PromptVariablesError(ConfigurationError):
    code = "prompt_variables_invalid"


class PolicyClauseNotFoundError(ConfigurationError):
    code = "policy_clause_not_found"


class PolicyBindingMissingError(ConfigurationError):
    code = "policy_binding_missing"


class PolicyPackInvalidError(ConfigurationError):
    code = "policy_pack_invalid"


class RetrievalIndexError(ConfigurationError):
    """A retrieval index is missing, malformed, or built for another pack version, corpus, or model."""

    code = "retrieval_index_invalid"


class EmbeddingBackendUnavailableError(ConfigurationError):
    """Dense retrieval was selected but the optional ``ml`` extra (sentence-transformers) is not installed."""

    code = "embedding_backend_unavailable"


class RetrievalNotAllowedError(ConfigurationError):
    """Open retrieval was requested outside the informational intent, a programming error in the caller."""

    code = "retrieval_not_allowed"


def all_error_types() -> list[type[DomainError]]:
    """Every class in the taxonomy, depth first from ``DomainError``."""
    found: list[type[DomainError]] = []
    pending: list[type[DomainError]] = [DomainError]
    while pending:
        current = pending.pop()
        found.append(current)
        pending.extend(current.__subclasses__())
    return found
