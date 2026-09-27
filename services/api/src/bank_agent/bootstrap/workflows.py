"""The workflow engines: the proposed system and baseline B0, each over its own validated registry.

Both share the same ports, tools, policy kernel, grounding verifier, and handoff builder; only the definitions
differ. Registry validation runs here, at startup, so an enabled workflow without a definition, an unbound state,
or a tool the matrix does not allow stops the process. The router, resolver, language detector, and risk estimator
(``risk_estimator:score_band@1`` until phase 10) are selected by name from ``WorkflowSettings``; the evaluation
harness (phase 14) resolves ``engine("baseline_b0")``.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace

from bank_agent.adapters.models.keyword_router import KeywordIntentRouter
from bank_agent.adapters.models.lexical_language import LexicalLanguageDetector
from bank_agent.adapters.models.rules_resolver import RuleTransactionResolver
from bank_agent.adapters.models.score_band_risk import ScoreBandRiskEstimator
from bank_agent.application.engine.context import CreditPorts, EngineServices, EngineSettings, ToolProvider
from bank_agent.application.engine.definition import WorkflowDefinition
from bank_agent.application.engine.engine import WorkflowEngine
from bank_agent.application.engine.registry import build_registry
from bank_agent.application.engine.render import Renderer
from bank_agent.application.workflows.account_inquiry.definition import build_account_inquiry
from bank_agent.application.workflows.baseline.definitions import BASELINE_DEFINITIONS
from bank_agent.application.workflows.baseline.menu import MenuRouter
from bank_agent.application.workflows.card_support.definition import build_card_support
from bank_agent.application.workflows.credit.definition import build_credit
from bank_agent.application.workflows.dispute.definition import build_dispute
from bank_agent.bootstrap.policy import PolicyServices
from bank_agent.bootstrap.retrieval import GroundingServices
from bank_agent.bootstrap.settings import WorkflowSettings
from bank_agent.domain.errors import WorkflowRegistryError
from bank_agent.domain.locale import Language
from bank_agent.domain.workflow import WorkflowId
from bank_agent.domain.workflow_catalog import WORKFLOW_CATALOG
from bank_agent.ports.determinism import Clock, IdGenerator
from bank_agent.ports.llm import LLMClient
from bank_agent.ports.models import IntentRouter, LanguageDetector, RiskEstimator, TransactionResolver
from bank_agent.ports.sessions import SessionStore
from bank_agent.ports.unit_of_work import UnitOfWorkFactory

PROPOSED = "proposed"
BASELINE_B0 = "baseline_b0"
PROPOSED_DEFINITIONS: Mapping[WorkflowId, Callable[[], WorkflowDefinition]] = {
    WorkflowId.ACCOUNT_INQUIRY: build_account_inquiry,
    WorkflowId.DISPUTE: build_dispute,
    WorkflowId.CARD_SUPPORT: build_card_support,
    WorkflowId.CREDIT: build_credit,
}


@dataclass(frozen=True)
class WorkflowServices:
    engines: Mapping[str, WorkflowEngine]

    def engine(self, system: str = PROPOSED) -> WorkflowEngine:
        return self.engines[system]


def enabled_workflows(settings: WorkflowSettings) -> frozenset[WorkflowId]:
    try:
        return frozenset(WorkflowId(name) for name in settings.enabled)
    except ValueError:
        raise WorkflowRegistryError(f"WORKFLOW_ENABLED names an unknown workflow: {settings.enabled}") from None


def build_workflows(
    settings: WorkflowSettings,
    *,
    uow_factory: UnitOfWorkFactory,
    session_store: SessionStore,
    tools: ToolProvider,
    policy: PolicyServices,
    grounding: GroundingServices,
    llm: LLMClient,
    clock: Clock,
    ids: IdGenerator,
    environment: str,
    router: IntentRouter | None = None,
    resolver: TransactionResolver | None = None,
    language_detector: LanguageDetector | None = None,
    risk_estimator: RiskEstimator | None = None,
) -> WorkflowServices:
    enabled = enabled_workflows(settings)
    credit = CreditPorts(
        catalog=policy.catalog,
        eligibility=policy.eligibility,
        risk_estimator=risk_estimator or ScoreBandRiskEstimator(clock, ids),
    )
    services = EngineServices(
        uow_factory=uow_factory,
        session_store=session_store,
        tools=tools,
        policy=policy,
        bound=grounding.bound,
        verifier=grounding.verifier,
        informational=grounding.informational,
        llm=llm,
        router=router or KeywordIntentRouter(),
        resolver=resolver or RuleTransactionResolver(),
        language_detector=language_detector or LexicalLanguageDetector(),
        clock=clock,
        ids=ids,
        credit=credit,
    )
    renderer = Renderer(policy.pack, grounding.verifier)
    proposed = EngineSettings(
        enabled=enabled,
        llm_understanding=settings.llm_understanding,
        llm_phrasing=settings.llm_phrasing,
        llm_handoff_summary=settings.llm_handoff_summary,
        max_turns=settings.max_turns,
        environment=environment,
    )
    baseline = EngineSettings(
        enabled=enabled,
        llm_understanding=False,
        max_turns=settings.max_turns,
        environment=environment,
        fixed_language=Language.ES,
        menu_template="b0.menu",
    )
    systems = (
        (PROPOSED, PROPOSED_DEFINITIONS, services, proposed),
        (BASELINE_B0, BASELINE_DEFINITIONS, replace(services, router=MenuRouter(services.router)), baseline),
    )
    engines: dict[str, WorkflowEngine] = {}
    for system, factories, system_services, engine_settings in systems:
        definitions = {workflow: factories[workflow]() for workflow in enabled if workflow in factories}
        registry = build_registry(
            system, definitions, catalog=WORKFLOW_CATALOG, bound=grounding.bound, pack=policy.pack, enabled=enabled
        )
        engines[system] = WorkflowEngine(system_services, engine_settings, registry, renderer)
    return WorkflowServices(engines)
