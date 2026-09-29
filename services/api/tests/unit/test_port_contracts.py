"""Every port is a documented Protocol, and every implementation satisfies its port.

The typed assignments below are checked by mypy (structural conformance); at runtime the test checks that
each port docstring states preconditions, postconditions, errors, and isolation.
"""

import importlib
import inspect
import pkgutil
from decimal import Decimal
from pathlib import Path

import pytest

import bank_agent.ports
from bank_agent.adapters.llm.budget import BudgetGuardDecorator, BudgetLimits
from bank_agent.adapters.llm.cassette import CassetteLLM
from bank_agent.adapters.llm.circuit_breaker import CircuitBreakerDecorator
from bank_agent.adapters.llm.client import PromptedLLMClient
from bank_agent.adapters.llm.cost import CostAccountingDecorator
from bank_agent.adapters.llm.fallback import FallbackDecorator
from bank_agent.adapters.llm.litellm_client import LiteLLMClient, LiteLLMCompletion
from bank_agent.adapters.llm.prices import PriceTable
from bank_agent.adapters.llm.redaction import RedactionDecorator, Redactor
from bank_agent.adapters.llm.retry import BoundedRetryDecorator
from bank_agent.adapters.llm.timeout import TimeoutDecorator
from bank_agent.adapters.llm.tracing import TracingDecorator
from bank_agent.adapters.llm.unconfigured import UnconfiguredLLMClient
from bank_agent.adapters.persistence.memory.sessions import InMemorySessionStore
from bank_agent.adapters.persistence.memory.store import InMemoryStore
from bank_agent.adapters.persistence.memory.unit_of_work import InMemoryUnitOfWorkFactory, standalone_audit_log
from bank_agent.adapters.prompts.file_registry import FilePromptRegistry
from bank_agent.adapters.system.clock import SystemClock
from bank_agent.adapters.system.ids import RandomIdGenerator
from bank_agent.adapters.telemetry.noop import NoopTelemetry
from bank_agent.bootstrap.settings import DEFAULT_PRICES_FILE
from bank_agent.ports.audit import AuditLog
from bank_agent.ports.determinism import Clock, IdGenerator
from bank_agent.ports.llm import LLMClient
from bank_agent.ports.models import IntentRouter, LanguageDetector, TransactionResolver
from bank_agent.ports.prompts import PromptRegistry
from bank_agent.ports.sessions import SessionStore
from bank_agent.ports.telemetry import Telemetry
from bank_agent.ports.unit_of_work import UnitOfWorkFactory
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.fake_llm import FakeLLM
from bank_agent.testing.ids import SequentialIdGenerator
from bank_agent.testing.language import FakeLanguageDetector
from bank_agent.testing.models import FakeIntentRouter, FakeTransactionResolver
from bank_agent.testing.telemetry import RecordingTelemetry

SECTIONS = ("Preconditions:", "Postconditions:", "Errors:", "Isolation:")
# Protocols that only extend a documented reader, or are parts of a larger port.
EXTENSIONS = {
    "CustomerRepository",
    "ProductRepository",
    "TransactionRepository",
    "HistoricalComplaintRepository",
    "Span",
    "Counter",
    "Histogram",
    "Gauge",
}


def _port_protocols() -> list[type]:
    found: list[type] = []
    for module_info in pkgutil.walk_packages(bank_agent.ports.__path__, "bank_agent.ports."):
        module = importlib.import_module(module_info.name)
        for obj in vars(module).values():
            if inspect.isclass(obj) and getattr(obj, "_is_protocol", False) and obj.__module__ == module.__name__:
                found.append(obj)
    return found


PORTS = _port_protocols()


def test_finds_every_port() -> None:
    names = {port.__name__ for port in PORTS}
    assert {"UnitOfWork", "SessionStore", "LLMClient", "PolicyRepository", "Retriever", "ModelRegistry"} <= names
    assert len(PORTS) >= 30


@pytest.mark.parametrize("port", [p for p in PORTS if p.__name__ not in EXTENSIONS], ids=lambda p: p.__name__)
def test_port_docstring_states_the_full_contract(port: type) -> None:
    doc = port.__doc__ or ""
    missing = [section for section in SECTIONS if section not in doc]
    assert not missing, f"{port.__name__} docstring lacks {missing}"


def test_implementations_satisfy_their_ports() -> None:
    store = InMemoryStore()
    clocks: list[Clock] = [SystemClock(), FixedClock(SystemClock().now())]
    ids: list[IdGenerator] = [RandomIdGenerator(), SequentialIdGenerator()]
    uow_factory: UnitOfWorkFactory = InMemoryUnitOfWorkFactory(store)
    sessions: SessionStore = InMemorySessionStore()
    audit: AuditLog = standalone_audit_log(store)
    llm: LLMClient = FakeLLM()
    router: IntentRouter = FakeIntentRouter()
    resolver: TransactionResolver = FakeTransactionResolver()
    detector: LanguageDetector = FakeLanguageDetector()
    telemetry: list[Telemetry] = [NoopTelemetry(), RecordingTelemetry()]
    assert all(
        item is not None
        for item in (clocks, ids, uow_factory, sessions, audit, llm, router, resolver, detector, telemetry)
    )


def test_llm_gateway_implementations_satisfy_their_ports(tmp_path: Path) -> None:
    registry: PromptRegistry = FilePromptRegistry.from_package()
    clock = FixedClock(SystemClock().now())
    telemetry = RecordingTelemetry()
    base = FakeLLM()
    prices = PriceTable.from_yaml(DEFAULT_PRICES_FILE)
    limits = BudgetLimits(
        session_token_limit=1, conversation_cost_limit_usd=Decimal(1), daily_cost_limit_usd=Decimal(1)
    )
    clients: list[LLMClient] = [
        PromptedLLMClient(registry, LiteLLMCompletion("a/b", api_key=None, timeout_seconds=1)),
        LiteLLMClient(registry, model="a/b", api_key=None, timeout_seconds=1),
        CassetteLLM(tmp_path, model_id="a/b", redactor=Redactor(), clock=clock),
        UnconfiguredLLMClient(),
        RedactionDecorator(base, redactor=Redactor()),
        BudgetGuardDecorator(base, limits=limits, prices=prices, model_ids=("a/b",), clock=clock),
        TracingDecorator(base, telemetry=telemetry, provider_name="a", request_model="a/b"),
        CostAccountingDecorator(base, prices=prices, telemetry=telemetry),
        FallbackDecorator(base, FakeLLM()),
        CircuitBreakerDecorator(base, clock=clock),
        BoundedRetryDecorator(base),
        TimeoutDecorator(base, seconds=1),
    ]
    assert len(clients) == 12
