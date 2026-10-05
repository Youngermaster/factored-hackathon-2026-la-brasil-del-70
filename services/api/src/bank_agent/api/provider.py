"""What the HTTP layer needs from the composition root, expressed as a Protocol.

``bank_agent.api`` and ``bank_agent.bootstrap`` are independent layers, so the API never imports the
container. The container in ``bootstrap/container.py`` satisfies this Protocol structurally, and the entry
point in ``bank_agent.asgi`` passes it to ``create_app`` together with an ``ApiConfig`` built from settings.
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from bank_agent.api.config import SecurityConfig
from bank_agent.application.agent.inbox import AgentInbox
from bank_agent.application.conversations.human_service import HumanService
from bank_agent.application.conversations.service import ConversationService
from bank_agent.application.identity.sessions import SessionService
from bank_agent.domain.identifiers import CreditProductCode
from bank_agent.domain.locale import Language
from bank_agent.domain.model_inventory import ModelInventory
from bank_agent.domain.policy import PolicyClause
from bank_agent.policy.loader.catalog import ProductDisplay
from bank_agent.ports.determinism import Clock
from bank_agent.ports.evaluation import EvaluationSummaryReader, ModelCardReader
from bank_agent.ports.health import ReadinessCheck
from bank_agent.ports.rate_limits import RateLimitStore
from bank_agent.ports.reliability import DegradationSource
from bank_agent.ports.telemetry import Telemetry


def no_trace() -> str | None:
    return None


@dataclass(frozen=True, slots=True)
class ApiConfig:
    """HTTP-layer configuration derived from settings by the composition root."""

    request_id_factory: Callable[[], str]
    version: str
    title: str = "bank-agent"
    expose_docs: bool = True
    readiness_timeout_seconds: float = 2.0
    security: SecurityConfig = field(default_factory=SecurityConfig.development)
    monotonic: Callable[[], float] = time.monotonic
    """The clock of the in-process rate limiter's windows; tests pass a controllable one."""
    rate_limit_store: RateLimitStore | None = None
    """Where rate-limit counters live; ``None`` keeps them in this process (the shared store in production)."""
    database_retry_after_seconds: int = 30
    """``Retry-After`` on the 503 while the database is unavailable (``DEGRADATION_DATABASE_RETRY_AFTER_SECONDS``)."""
    current_trace_id: Callable[[], str | None] = no_trace
    """The active trace id for ``X-Trace-Id`` (the telemetry adapter's ``current_trace_id``)."""


class CreditProductNames(Protocol):
    """The catalog's es, pt, and en product names and summaries (``FilesystemCreditCatalog`` satisfies it).

    Display text stays out of the ``CreditProductCatalog`` port; only the HTTP layer names products for people.
    """

    def display(self, code: CreditProductCode, language: Language) -> ProductDisplay | None: ...


class PolicyClauses(Protocol):
    """Clause lookup in the loaded policy pack (``FilesystemPolicyRepository`` and ``PolicyPack`` satisfy it).

    The agent console renders a handoff's policy basis with it; ``PolicyClauseNotFoundError`` for an unknown clause.
    """

    def get_clause(self, clause_id: str, language: Language, version: int | None = None) -> PolicyClause: ...


class ServiceProvider(Protocol):
    """Services the HTTP layer resolves: identity, conversations, the agent inbox, evaluation summaries, and the
    model inventory with its model cards."""

    @property
    def clock(self) -> Clock:
        """The clock sessions and cookies are computed against."""
        ...

    @property
    def session_service(self) -> SessionService | None:
        """Login, step-up, and sessions; ``None`` until ``SESSION_SECRET`` is set (auth routes answer 503)."""
        ...

    @property
    def conversations(self) -> ConversationService: ...

    @property
    def inbox(self) -> AgentInbox: ...

    @property
    def human_service(self) -> HumanService: ...

    @property
    def evaluation_summaries(self) -> EvaluationSummaryReader: ...

    @property
    def model_inventory(self) -> ModelInventory:
        """What the process serves (models, language model setup, prompts, policy pack), recorded at startup."""
        ...

    @property
    def model_cards(self) -> ModelCardReader:
        """The curated offline model cards and promotion decisions."""
        ...

    @property
    def credit_product_names(self) -> CreditProductNames:
        """Product names for the credit product parts of assistant messages."""
        ...

    @property
    def policy_clauses(self) -> PolicyClauses:
        """The loaded policy pack's clauses, for the excerpts of a handoff's policy basis."""
        ...

    @property
    def readiness_checks(self) -> Sequence[ReadinessCheck]:
        """Dependencies checked by ``/health/ready``; empty when none are configured."""
        ...

    @property
    def telemetry(self) -> Telemetry:
        """Where the HTTP layer's metrics go (rate-limit rejections, active sessions)."""
        ...

    @property
    def degradation(self) -> DegradationSource:
        """The degradation ladder read by ``/health/details`` and told the outcome of each database probe."""
        ...

    async def aclose(self) -> None:
        """Release pooled resources such as database engines. Called once at application shutdown."""
        ...
