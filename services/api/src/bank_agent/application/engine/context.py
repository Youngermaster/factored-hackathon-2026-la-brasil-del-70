"""The ports the engine uses, its settings, the per-turn context handlers receive, and the ``Step`` they return."""

from dataclasses import dataclass, field
from datetime import date, datetime, tzinfo
from typing import Protocol

from pydantic import JsonValue

from bank_agent.application.engine.data import EngineData
from bank_agent.application.engine.definition import WorkflowDefinition
from bank_agent.application.engine.recorder import TurnRecorder
from bank_agent.application.engine.reply import Reply
from bank_agent.application.engine.tools import GuardedToolset
from bank_agent.application.grounding.bound import BoundPolicy, BoundPolicyLookup
from bank_agent.application.grounding.retrieval import InformationalRetrieval
from bank_agent.application.grounding.verifier import GroundingVerifier
from bank_agent.application.tools.banking import SessionToolset
from bank_agent.application.tools.base import ToolDependencies
from bank_agent.application.tools.context import SessionContext
from bank_agent.application.tools.verification import WriteVerifier
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.conversation import Conversation
from bank_agent.domain.customer import Customer
from bank_agent.domain.decision import Decision
from bank_agent.domain.handoff import Handoff
from bank_agent.domain.identifiers import TransactionId, TurnId
from bank_agent.domain.intelligence import IntentPrediction, LanguageDetection
from bank_agent.domain.locale import Language, Locale
from bank_agent.domain.money import Currency
from bank_agent.domain.session import Session, SessionSnapshot
from bank_agent.domain.trust import TrustState
from bank_agent.domain.workflow import Outcome, WorkflowId, WorkflowRef
from bank_agent.policy.facts import EscalationSignals, EvaluationRequest, PrivacySignals
from bank_agent.policy.pack import PolicyPack
from bank_agent.ports.determinism import Clock, IdGenerator
from bank_agent.ports.llm import LLMClient
from bank_agent.ports.models import IntentRouter, LanguageDetector, TransactionResolver
from bank_agent.ports.sessions import SessionStore
from bank_agent.ports.unit_of_work import UnitOfWorkFactory


class ToolProvider(Protocol):
    """``BankingTools`` satisfies it; tests and evaluations wrap it (the failure injector) the same way."""

    def for_session(self, context: SessionContext) -> SessionToolset: ...

    @property
    def dependencies(self) -> ToolDependencies: ...


class PolicyEvaluator(Protocol):
    """The loaded policy pack and the pure kernel (``bootstrap.policy.PolicyServices`` satisfies it)."""

    @property
    def pack(self) -> PolicyPack: ...

    @property
    def data_as_of(self) -> date: ...

    def evaluate(self, request: EvaluationRequest) -> Decision: ...


@dataclass(frozen=True)
class EngineSettings:
    enabled: frozenset[WorkflowId]
    llm_understanding: bool = True
    llm_phrasing: bool = False
    llm_handoff_summary: bool = False
    max_turns: int = 40
    max_steps: int = 12
    llm_max_output_tokens: int = 600
    environment: str = "development"
    fixed_language: Language | None = None
    """Baseline B0 answers in one fixed language whatever the customer writes."""
    menu_template: str | None = None
    """Baseline B0 shows a fixed menu instead of the greeting and the workflow question."""


@dataclass(frozen=True)
class EngineServices:
    uow_factory: UnitOfWorkFactory
    session_store: SessionStore
    tools: ToolProvider
    policy: PolicyEvaluator
    bound: BoundPolicyLookup
    verifier: GroundingVerifier
    informational: InformationalRetrieval
    llm: LLMClient
    router: IntentRouter
    resolver: TransactionResolver
    language_detector: LanguageDetector
    clock: Clock
    ids: IdGenerator


@dataclass(frozen=True)
class Step:
    """Where the conversation goes next. With a reply the turn ends; without one the next handler runs."""

    next_state: str
    reply: Reply | None = None
    outcome: Outcome = Outcome.IN_PROGRESS
    unanswered: bool = False
    """The handler expected an answer (yes or no, an option) and could not parse one; ``reply`` asks again and the
    engine may still route the text to a switch, a handoff, or a shared answer."""


@dataclass
class TurnContext:
    services: EngineServices
    settings: EngineSettings
    turn_id: TurnId
    text: UntrustedText
    session: Session
    session_context: SessionContext | None
    snapshot: SessionSnapshot
    trust: TrustState
    customer: Customer
    conversation: Conversation
    language: Language
    now: datetime
    today: date
    zone: tzinfo
    definition: WorkflowDefinition
    state: str
    engine: EngineData
    recorder: TurnRecorder
    tools: GuardedToolset
    flow: dict[str, JsonValue] = field(default_factory=dict)
    clarifications_used: int = 0
    turns_used: int = 0
    prediction: IntentPrediction | None = None
    detection: LanguageDetection | None = None
    escalation: EscalationSignals = field(default_factory=EscalationSignals)
    privacy: PrivacySignals = field(default_factory=PrivacySignals)
    handoff: Handoff | None = None
    workflow_before: WorkflowRef | None = None
    enabled: tuple[WorkflowId, ...] = ()
    at_router: bool = False
    """The conversation has not been dispatched to a workflow yet (position ``router@1``)."""
    currency: Currency | None = None
    """The account currency, when the customer's products share one (a bare ``$`` resolves to it)."""
    referenced_transaction: TransactionId | None = None
    """A transaction id the customer named that belongs to the session customer (checked by the engine)."""
    prior_complaints: int = 0
    resumed: bool = False
    reprompt: bool = False
    """Ask the state's question again without parsing the text (after a resume or a declined switch)."""

    @property
    def locale(self) -> Locale:
        return Locale.for_customer(self.customer.country, self.language)

    @property
    def workflow(self) -> WorkflowId:
        return self.definition.workflow

    @property
    def policy_state(self) -> str:
        return self.definition.spec(self.state).policy_state

    def bound(self, policy_state: str | None = None) -> BoundPolicy:
        state = policy_state or self.policy_state
        return self.services.bound.for_state(self.workflow, state, self.customer, self.language)

    def write_verifier(self) -> WriteVerifier:
        if self.session_context is None:
            raise RuntimeError("no verified session to read back with")
        return WriteVerifier(self.services.tools.dependencies, self.session_context)
