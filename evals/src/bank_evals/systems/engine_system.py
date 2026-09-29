"""P (the proposed system) and B0 (the menu and rules bot): the application core, in process.

Both come from the composition root's builders: the policy pack and the synthetic eligibility service
(``build_policy``), bound clauses, retrieval, and the grounding verifier (``build_grounding``), the language model
gateway (``build_llm_client``), and the engines (``build_workflows``), over the in-memory persistence adapters,
which pass the same contract suites as PostgreSQL. Each case gets a fresh store seeded with its copy of the
evaluation world, its own fixed clock and identifiers, and its tools (with the scheduled failures of its plan).
"""

from __future__ import annotations

import hashlib
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import timedelta

from bank_agent.adapters.persistence.duckdb.gold import DATASET_CREDIT_BALANCE_CONVENTION
from bank_agent.adapters.persistence.memory.sessions import InMemorySessionStore
from bank_agent.adapters.persistence.memory.store import InMemoryStore
from bank_agent.adapters.persistence.memory.unit_of_work import InMemoryUnitOfWorkFactory
from bank_agent.application.engine.context import ToolProvider
from bank_agent.application.engine.engine import TurnRequest, WorkflowEngine
from bank_agent.application.tools.banking import BankingTools
from bank_agent.application.tools.base import ToolDependencies
from bank_agent.application.tools.context import ToolSettings
from bank_agent.bootstrap.models import EmbedderFactory, build_risk_estimator
from bank_agent.bootstrap.policy import PolicyServices
from bank_agent.bootstrap.retrieval import GroundingServices
from bank_agent.bootstrap.settings import WorkflowSettings
from bank_agent.bootstrap.workflows import BASELINE_B0, PROPOSED, build_workflows
from bank_agent.domain.access import AuthLevel, Role
from bank_agent.domain.eligibility import CreditRiskFeatures, RiskEstimate
from bank_agent.domain.errors import RiskEstimatorUnavailableError
from bank_agent.domain.identifiers import ConversationId, IdKind, TurnId
from bank_agent.domain.intelligence import ModelComponent
from bank_agent.domain.session import Session
from bank_agent.ports.llm import LLMClient
from bank_agent.ports.models import IntentRouter, ModelRegistry, RiskEstimator, TransactionResolver
from bank_agent.testing.clock import FixedClock
from bank_evals.scenarios.model import ModelUnavailable, Scenario
from bank_evals.systems.base import EndState, TurnView
from bank_evals.systems.failures import ScheduledFailureTools
from bank_evals.systems.schedule import FailureSchedule
from bank_evals.systems.views import end_state, turn_view
from bank_evals.world.fixtures import apply_fixtures
from bank_evals.world.model import NOW, World

ENVIRONMENT = "evaluation"
SYSTEM_VARIANTS = {"p": PROPOSED, "b0": BASELINE_B0}


class CaseIds:
    """Implements ``IdGenerator``: identifiers unique to one case and run, so no two cases share a conversation."""

    def __init__(self, tag: str) -> None:
        self._tag, self._counters = tag, Counter[IdKind]()

    def new(self, kind: IdKind) -> str:
        self._counters[kind] += 1
        return f"{kind.value}-{self._tag}{self._counters[kind]:05d}"


class UnavailableEstimator:
    """A ``RiskEstimator`` that cannot estimate, for the ``model_unavailable`` fixture (evaluation double)."""

    def estimate(self, features: CreditRiskFeatures) -> RiskEstimate:
        raise RiskEstimatorUnavailableError("evaluation fixture: the risk estimator is unavailable")


@dataclass(frozen=True)
class EngineParts:
    """What every case of a run shares: built once from settings by the composition root's builders."""

    settings: WorkflowSettings
    policy: PolicyServices
    grounding: GroundingServices
    llm: LLMClient
    models: ModelRegistry
    router: IntentRouter
    resolver: TransactionResolver
    embedder: EmbedderFactory | None = None
    model_label: str = "none"


@dataclass
class EngineCase:
    engine: WorkflowEngine
    store: InMemoryStore
    clock: FixedClock
    customer_id: str
    schedule: FailureSchedule
    tag: str
    before: EndState
    conversation: str | None = None
    session: Session = field(init=False)
    sessions: int = 0
    turns: int = 0

    def __post_init__(self) -> None:
        self.session = self._new_session(step_up=False)

    def _new_session(self, *, step_up: bool) -> Session:
        self.sessions += 1
        now = self.clock.now()
        current = Session(
            session_id=f"ses-{self.tag}-{self.sessions}",  # type: ignore[arg-type]
            lineage_id=f"lin-{self.tag}",  # type: ignore[arg-type]
            role=Role.CUSTOMER,
            customer_id=self.customer_id,  # type: ignore[arg-type]
            auth_level=AuthLevel.OTP_VERIFIED,
            created_at=now,
            last_seen_at=now,
            idle_timeout=timedelta(minutes=15),
            absolute_expires_at=now + timedelta(minutes=60),
        )
        return current.with_step_up(now=now, until=now + timedelta(minutes=5)) if step_up else current

    async def send(self, text: str) -> TurnView:
        self.turns += 1
        turn_id = f"9e7a0000-0000-4000-8000-{self.tag[:4]}{self.turns:08d}"
        request = TurnRequest(
            turn_id=TurnId(turn_id),
            text=text,
            session=self.session,
            conversation_id=ConversationId(self.conversation) if self.conversation else None,
        )
        started = time.perf_counter()
        result = await self.engine.process_turn(request)
        latency = int((time.perf_counter() - started) * 1000)
        self.conversation = result.conversation_id
        record = self.store.execution_records.get(turn_id)
        return turn_view(self.turns, text, result, record, latency, self.customer_id)

    async def reauthenticate(self) -> None:
        self.session = self._new_session(step_up=False)

    async def step_up(self) -> None:
        self.session = self._new_session(step_up=True)

    def expire_session(self) -> None:
        self.clock.advance(timedelta(minutes=20))

    def advance_clock(self, seconds: int) -> None:
        self.clock.advance(timedelta(seconds=seconds))

    async def finish(self) -> EndState:
        return end_state(self.store, self.before)


class EngineSystem:
    """P or B0 over the shared ``EngineParts``."""

    def __init__(self, name: str, parts: EngineParts) -> None:
        if name not in SYSTEM_VARIANTS:
            raise ValueError(f"unknown engine system {name!r}")
        self.name, self._parts = name, parts

    @property
    def model_label(self) -> str:
        return self._parts.model_label if self.name == "p" else "none"

    async def start(self, scenario: Scenario, world: World, *, run_index: int) -> EngineCase:
        parts = self._parts
        case_world = apply_fixtures(scenario, world.copy())
        store = InMemoryStore()
        store.seed(
            customers=case_world.customers,
            products=case_world.products,
            transactions=case_world.transactions,
            complaints=case_world.complaints,
            cases=case_world.cases,
            credit_profiles=case_world.credit_profiles,
            credit_applications=case_world.credit_applications,
        )
        tag = hashlib.sha256(f"{scenario.id}:{self.name}:{run_index}".encode()).hexdigest()[:10]
        clock, ids = FixedClock(NOW), CaseIds(tag)
        uow_factory = InMemoryUnitOfWorkFactory(store)
        banking = BankingTools(
            ToolDependencies(
                uow_factory=uow_factory,
                catalog=parts.policy.catalog,
                clock=clock,
                ids=ids,
                settings=ToolSettings(
                    policy=parts.policy.tool_policy, balance_convention=DATASET_CREDIT_BALANCE_CONVENTION
                ),
            )
        )
        schedule = FailureSchedule(scenario.tool_failure_plan)
        tools: ToolProvider = ScheduledFailureTools(banking, schedule, environment=ENVIRONMENT)
        services = build_workflows(
            parts.settings,
            uow_factory=uow_factory,
            session_store=InMemorySessionStore(),
            tools=tools,
            policy=parts.policy,
            grounding=parts.grounding,
            llm=parts.llm,
            clock=clock,
            ids=ids,
            environment=ENVIRONMENT,
            router=parts.router,
            resolver=parts.resolver,
            risk_estimator=self._estimator(scenario, clock, ids),
            model_registry=parts.models,
            embedder=parts.embedder,
        )
        customer = case_world.persona(scenario.persona_ref).customer.customer_id
        return EngineCase(
            services.engine(SYSTEM_VARIANTS[self.name]),
            store,
            clock,
            customer,
            schedule,
            tag,
            before=end_state(store, None),
        )

    def _estimator(self, scenario: Scenario, clock: FixedClock, ids: CaseIds) -> RiskEstimator:
        unavailable = any(
            isinstance(f, ModelUnavailable) and f.component is ModelComponent.RISK_ESTIMATOR for f in scenario.fixtures
        )
        if unavailable:
            return UnavailableEstimator()
        return build_risk_estimator(self._parts.settings, self._parts.models, clock, ids)
