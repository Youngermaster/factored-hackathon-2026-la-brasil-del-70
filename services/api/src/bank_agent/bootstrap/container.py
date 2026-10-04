"""Composition root: the only module that knows concrete adapters.

The container turns settings into wired services. The HTTP layer consumes it through the
``bank_agent.api.provider.ServiceProvider`` Protocol, CLIs and the evaluation harness resolve from it
directly, and tests build it with their own settings. The language model gateway is built here from settings
(``bootstrap/llm.py``); tests and the evaluation harness inject a base client through ``LlmOverrides``. Later
phases add model clients here. Persistence, identity, and the banking tools come from ``bootstrap/persistence.py``;
the policy pack, the synthetic credit catalog, and the eligibility service from ``bootstrap/policy.py``; the bound
clause lookup, open retrieval, and the grounding verifier from ``bootstrap/retrieval.py`` (tests and the evaluation
harness may inject an embedder so dense retrieval runs without the optional ``ml`` extra); the workflow engines (the
proposed system and baseline B0) from ``bootstrap/workflows.py``; the HTTP use cases (conversations, the agent inbox,
the published evaluation summaries) are wired here too.
"""

from collections.abc import Callable, Sequence

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from bank_agent.adapters.evaluation.summaries import FilesystemEvaluationSummaries
from bank_agent.adapters.persistence.postgres.budget import PostgresBudgetLedger
from bank_agent.adapters.persistence.postgres.readiness import PostgresReadinessCheck
from bank_agent.adapters.policy.filesystem import FilesystemCreditCatalog, FilesystemPolicyRepository
from bank_agent.adapters.policy.unavailable import UnavailableCreditCatalog
from bank_agent.adapters.prompts.file_registry import FilePromptRegistry
from bank_agent.adapters.reliability.monitor import DatabaseHealth, DegradationMonitor
from bank_agent.adapters.retrieval.embedding import Embedder
from bank_agent.adapters.system.clock import SystemClock
from bank_agent.adapters.system.ids import RandomIdGenerator
from bank_agent.adapters.telemetry.noop import NoopTelemetry
from bank_agent.application.agent.inbox import AgentInbox
from bank_agent.application.conversations.human_service import HumanService
from bank_agent.application.conversations.service import ConversationService
from bank_agent.application.identity.sessions import SessionService
from bank_agent.application.preferences.service import AssistantPreferencesService
from bank_agent.application.reliability.ladder import LadderFlags
from bank_agent.application.tools.banking import BankingTools
from bank_agent.bootstrap.llm import LlmOverrides, build_llm_stack
from bank_agent.bootstrap.models import ModelFallbacks, default_embedder
from bank_agent.bootstrap.persistence import (
    PersistenceServices,
    build_banking_tools,
    build_persistence,
    build_rate_limit_store,
    build_session_service,
)
from bank_agent.bootstrap.policy import PolicyServices, build_policy
from bank_agent.bootstrap.retrieval import GroundingServices, build_grounding
from bank_agent.bootstrap.settings import AppSettings, DatabaseSettings, LLMSettings
from bank_agent.bootstrap.workflows import WorkflowServices, build_workflows
from bank_agent.domain.degradation import ComponentState
from bank_agent.domain.errors import ConfigurationError
from bank_agent.ports.budget import BudgetLedger
from bank_agent.ports.determinism import Clock, IdGenerator
from bank_agent.ports.evaluation import EvaluationSummaryReader
from bank_agent.ports.health import ReadinessCheck
from bank_agent.ports.llm import LLMClient
from bank_agent.ports.prompts import PromptRegistry
from bank_agent.ports.rate_limits import RateLimitStore
from bank_agent.ports.telemetry import Telemetry


def application_database_url(database: DatabaseSettings) -> URL:
    """Connection URL for the application role. Its string form masks the password."""
    password = database.app_password.get_secret_value() if database.app_password is not None else None
    return URL.create(
        drivername="postgresql+asyncpg",
        username=database.app_user,
        password=password,
        host=database.host,
        port=database.port,
        database=database.db,
    )


def budget_ledger(llm: LLMSettings, engine: AsyncEngine | None) -> BudgetLedger | None:
    """The shared PostgreSQL ledger when a database is configured (``LLM_BUDGET_LEDGER=auto`` or ``postgres``)."""
    if llm.budget_ledger == "memory":
        return None
    if engine is None:
        if llm.budget_ledger == "postgres":
            raise ConfigurationError("LLM_BUDGET_LEDGER=postgres needs the database settings")
        return None
    return PostgresBudgetLedger(engine)


class Container:
    """Wired services for one process. Satisfies ``ServiceProvider`` structurally."""

    def __init__(
        self,
        settings: AppSettings,
        *,
        clock: Clock | None = None,
        telemetry: Telemetry | None = None,
        llm_overrides: LlmOverrides | None = None,
        ids: IdGenerator | None = None,
        embedder: Embedder | None = None,
        persistence: PersistenceServices | None = None,
        on_close: Sequence[Callable[[], None]] = (),
    ) -> None:
        self.settings = settings
        self._on_close = tuple(on_close)
        self._clock: Clock = clock if clock is not None else SystemClock()
        self._telemetry: Telemetry = telemetry if telemetry is not None else NoopTelemetry()
        self._prompt_registry = FilePromptRegistry.from_package()
        self._engine: AsyncEngine | None = None
        if settings.database.is_configured:
            self._engine = create_async_engine(
                application_database_url(settings.database),
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=5,
            )
        degradation = settings.degradation
        self._llm_stack = build_llm_stack(
            settings.llm,
            registry=self._prompt_registry,
            clock=self._clock,
            telemetry=self._telemetry,
            overrides=llm_overrides,
            fallback_enabled=degradation.fallback_provider,
            ledger=budget_ledger(settings.llm, self._engine),
        )
        self._llm_client = self._llm_stack.client
        self._ids: IdGenerator = ids if ids is not None else RandomIdGenerator()
        self._database_health = DatabaseHealth(self._telemetry) if self._engine is not None else None
        self._persistence = (
            persistence if persistence is not None else build_persistence(self._engine, self._database_health)
        )
        self._session_service = build_session_service(settings, self._persistence, clock=self._clock, ids=self._ids)
        self._rate_limit_store = build_rate_limit_store(settings, self._engine, self._clock)
        self._policy = build_policy(
            settings.policy, clock=self._clock, ids=self._ids, catalog_fallback=degradation.credit_catalog_fallback
        )
        self._readiness_checks: tuple[ReadinessCheck, ...] = (
            (PostgresReadinessCheck(self._engine),) if self._engine is not None else ()
        )
        self._model_fallbacks = ModelFallbacks(
            baselines_allowed=degradation.model_baselines,
            router_threshold=degradation.router_threshold,
            risk_band_fallback=degradation.risk_band_fallback,
        )
        self._degradation = DegradationMonitor(
            clock=self._clock,
            telemetry=self._telemetry,
            flags=LadderFlags(
                fallback_provider=degradation.fallback_provider,
                template_only=degradation.template_only,
                model_baselines=degradation.model_baselines,
                risk_band_fallback=degradation.risk_band_fallback,
            ),
            llm=self._llm_stack.health,
            models_on_baseline=self._model_fallbacks.served_baseline,
            credit_catalog=ComponentState.OK if self._policy.credit_catalog_available else ComponentState.UNAVAILABLE,
            database=self._database_health if self._readiness_checks else None,
        )
        self._grounding = build_grounding(settings.retrieval, self._policy.repository, embedder=embedder)
        self._banking_tools = build_banking_tools(
            self._persistence,
            clock=self._clock,
            ids=self._ids,
            catalog=self._policy.catalog,
            tool_policy=self._policy.tool_policy,
        )
        self._workflows = build_workflows(
            settings.workflow,
            uow_factory=self._persistence.uow_factory,
            session_store=self._persistence.session_store,
            tools=self._banking_tools,
            policy=self._policy,
            grounding=self._grounding,
            llm=self._llm_client,
            clock=self._clock,
            ids=self._ids,
            environment=settings.runtime.app_env,
            embedder=(lambda: embedder) if embedder is not None else default_embedder(settings.retrieval),
            telemetry=self._telemetry,
            fallbacks=self._model_fallbacks,
            degradation=self._degradation,
        )
        self._conversations = ConversationService(
            self._workflows.engine(), self._persistence.uow_factory, self._clock, self._ids
        )
        self._assistant_preferences = AssistantPreferencesService(self._persistence.uow_factory, self._clock)
        self._inbox = AgentInbox(self._persistence.uow_factory, self._clock, self._ids)
        self._human_service = HumanService(self._persistence.uow_factory, self._clock, self._ids)
        self._evaluation_summaries = FilesystemEvaluationSummaries(settings.evaluation.summaries_dir)
        self._degradation.current()

    @property
    def credit_product_names(self) -> FilesystemCreditCatalog | UnavailableCreditCatalog:
        return self._policy.catalog

    @property
    def policy_clauses(self) -> FilesystemPolicyRepository:
        return self._policy.repository

    @property
    def readiness_checks(self) -> Sequence[ReadinessCheck]:
        return self._readiness_checks

    @property
    def degradation(self) -> DegradationMonitor:
        """The degradation ladder over the gateway's breakers and budget, startup loads, and database probes."""
        return self._degradation

    @property
    def clock(self) -> Clock:
        return self._clock

    @property
    def telemetry(self) -> Telemetry:
        return self._telemetry

    @property
    def prompt_registry(self) -> PromptRegistry:
        return self._prompt_registry

    @property
    def llm_client(self) -> LLMClient:
        """The fully decorated language model gateway."""
        return self._llm_client

    @property
    def persistence(self) -> PersistenceServices:
        """The unit of work factory, session store, audit log, and challenge store (PostgreSQL or memory)."""
        return self._persistence

    @property
    def session_service(self) -> SessionService | None:
        """Login, step-up, and sessions; ``None`` until ``SESSION_SECRET`` is set."""
        return self._session_service

    @property
    def policy(self) -> PolicyServices:
        """The policy pack, the synthetic catalog, the eligibility service, and the data as-of date."""
        return self._policy

    @property
    def grounding(self) -> GroundingServices:
        """The bound clause lookup, informational retrieval with abstention, and the grounding verifier."""
        return self._grounding

    @property
    def banking_tools(self) -> BankingTools:
        return self._banking_tools

    @property
    def workflows(self) -> WorkflowServices:
        """The workflow engines: ``engine()`` is the proposed system, ``engine("baseline_b0")`` baseline B0."""
        return self._workflows

    @property
    def conversations(self) -> ConversationService:
        """Open, send, history, and trace over the proposed system's engine."""
        return self._conversations

    @property
    def assistant_preferences(self) -> AssistantPreferencesService:
        return self._assistant_preferences

    @property
    def inbox(self) -> AgentInbox:
        return self._inbox

    @property
    def human_service(self) -> HumanService:
        return self._human_service

    @property
    def evaluation_summaries(self) -> EvaluationSummaryReader:
        return self._evaluation_summaries

    @property
    def rate_limit_store(self) -> RateLimitStore | None:
        """The shared rate-limit store, or ``None`` when the HTTP layer keeps its counters in this process."""
        return self._rate_limit_store

    @property
    def database_engine(self) -> AsyncEngine | None:
        """The application-role engine, or ``None`` when no database is configured."""
        return self._engine

    async def aclose(self) -> None:
        """Dispose of the database engine, then run the shutdown hooks (flushing the telemetry exporters)."""
        try:
            if self._engine is not None:
                await self._engine.dispose()
        finally:
            for close in self._on_close:
                close()
