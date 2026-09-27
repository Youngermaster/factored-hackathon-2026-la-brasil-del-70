"""Workflow scenario support: the backends (in-memory adapters and PostgreSQL) and assertion helpers."""

import json
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from bank_agent.adapters.persistence.memory.sessions import InMemorySessionStore
from bank_agent.adapters.persistence.memory.store import InMemoryStore
from bank_agent.adapters.persistence.memory.unit_of_work import InMemoryUnitOfWorkFactory
from bank_agent.adapters.persistence.postgres.seed import PostgresSeeder, SeedBundle
from bank_agent.adapters.persistence.postgres.sessions import PostgresSessionStore
from bank_agent.adapters.persistence.postgres.unit_of_work import PostgresUnitOfWorkFactory
from bank_agent.domain.dispute import DisputeCase
from bank_agent.domain.handoff import Handoff
from bank_agent.domain.intelligence import PromptRef
from bank_agent.domain.session import Session
from bank_agent.ports.sessions import SessionStore
from bank_agent.ports.unit_of_work import UnitOfWorkFactory
from bank_agent.testing.fake_llm import FakeLLM, ScriptedResponse
from bank_agent_postgres import app_engine, owner_engine, reset_database
from bank_agent_scenarios import scenario_data
from bank_agent_test_support import PostgresInstance
from bank_agent_workflows import Harness


@dataclass
class Backend:
    uow_factory: UnitOfWorkFactory
    session_store: SessionStore


async def memory_backend(request: pytest.FixtureRequest) -> AsyncIterator[Backend]:
    data = scenario_data()
    store = InMemoryStore()
    store.seed(
        customers=data.customers,
        products=data.products,
        transactions=data.transactions,
        cases=data.cases,
        credit_profiles=data.credit_profiles,
    )
    yield Backend(InMemoryUnitOfWorkFactory(store), InMemorySessionStore())


async def postgres_backend(request: pytest.FixtureRequest) -> AsyncIterator[Backend]:
    instance: PostgresInstance = request.getfixturevalue("migrated_postgres")
    await reset_database(instance)
    data = scenario_data()
    owner = owner_engine(instance)
    try:
        bundle = SeedBundle(
            customers=data.customers,
            products=data.products,
            transactions=data.transactions,
            cases=data.cases,
            credit_profiles=data.credit_profiles,
        )
        await PostgresSeeder(owner).load(bundle)
    finally:
        await owner.dispose()
    engine = app_engine(instance)
    try:
        yield Backend(PostgresUnitOfWorkFactory(engine), PostgresSessionStore(engine))
    finally:
        await engine.dispose()


BACKENDS: dict[str, Callable[[pytest.FixtureRequest], AsyncIterator[Backend]]] = {
    "memory": memory_backend,
    "postgres": postgres_backend,
}


SCHEMA = Path(__file__).resolve().parents[3] / "contracts" / "schemas" / "handoff.v1.json"
NO_SIGNALS = {"legal_or_regulator_mention": False, "distress": False, "human_requested": False,
              "third_party_admission": False}  # fmt: skip
SIGNALS = PromptRef(prompt_id="detect_escalation_signals", version=1)
DISPUTE_SLOTS = PromptRef(prompt_id="extract_dispute_slots", version=1)
CARD_SLOTS = PromptRef(prompt_id="extract_card_support_slots", version=1)
ACCOUNT_SLOTS = PromptRef(prompt_id="extract_account_inquiry_slots", version=1)
CREDIT_SLOTS = PromptRef(prompt_id="extract_credit_slots", version=1)
PHRASE = PromptRef(prompt_id="phrase_response", version=1)


def assert_schema_valid(handoff: Handoff) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(handoff.model_dump(mode="json")))
    assert errors == []


def assert_no_transcript(handoff: Handoff, *texts: str) -> None:
    dumped = handoff.model_dump_json()
    for text in texts:
        assert text not in dumped


async def cases(harness: Harness, session: Session) -> Sequence[DisputeCase]:
    async with harness.uow_factory(session.access_context()) as uow:
        return await uow.cases.list()


def scripted_llm(dispute: dict[str, Any] | None = None, card: dict[str, Any] | None = None) -> FakeLLM:
    fake = FakeLLM()
    fake.script(SIGNALS, ScriptedResponse(output=NO_SIGNALS))
    if dispute is not None:
        fake.script(DISPUTE_SLOTS, ScriptedResponse(output=dispute))
    if card is not None:
        fake.script(CARD_SLOTS, ScriptedResponse(output=card))
    return fake
