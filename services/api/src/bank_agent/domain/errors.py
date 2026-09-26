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


class ModelArtifactNotFoundError(DependencyError):
    code = "model_artifact_not_found"


class ModelArtifactIntegrityError(DependencyError):
    code = "model_artifact_integrity"


# --- Configuration -------------------------------------------------------------------------------------------


class ConfigurationError(DomainError):
    code = "configuration_error"


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


def all_error_types() -> list[type[DomainError]]:
    """Every class in the taxonomy, depth first from ``DomainError``."""
    found: list[type[DomainError]] = []
    pending: list[type[DomainError]] = [DomainError]
    while pending:
        current = pending.pop()
        found.append(current)
        pending.extend(current.__subclasses__())
    return found
