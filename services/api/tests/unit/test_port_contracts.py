"""Every port is a documented Protocol, and every implementation satisfies its port.

The typed assignments below are checked by mypy (structural conformance); at runtime the test checks that
each port docstring states preconditions, postconditions, errors, and isolation.
"""

import importlib
import inspect
import pkgutil

import pytest

import bank_agent.ports
from bank_agent.adapters.persistence.memory.sessions import InMemorySessionStore
from bank_agent.adapters.persistence.memory.store import InMemoryStore
from bank_agent.adapters.persistence.memory.unit_of_work import InMemoryUnitOfWorkFactory, standalone_audit_log
from bank_agent.adapters.system.clock import SystemClock
from bank_agent.adapters.system.ids import RandomIdGenerator
from bank_agent.adapters.telemetry.noop import NoopTelemetry
from bank_agent.ports.audit import AuditLog
from bank_agent.ports.determinism import Clock, IdGenerator
from bank_agent.ports.llm import LLMClient
from bank_agent.ports.models import IntentRouter, LanguageDetector, TransactionResolver
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
