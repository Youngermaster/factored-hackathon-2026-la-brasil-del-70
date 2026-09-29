"""``bank-data seed`` against the migrated test PostgreSQL, from fixture gold files (the contract dataset)."""

from datetime import date
from pathlib import Path

import asyncpg
import pytest
from sqlalchemy import text

from bank_agent.adapters.identity.codes import IdentityKeys
from bank_agent.adapters.persistence.postgres.database import DatabaseRole, open_transaction
from bank_agent.domain.locale import Country
from bank_agent_contracts import ContractDataset, contract_dataset
from bank_agent_duckdb import SNAPSHOT, write_gold, write_table
from bank_agent_postgres import owner_engine, reset_database
from bank_agent_test_support import PostgresInstance
from bank_data.errors import SeedVerificationError
from bank_data.seed.config import load_personas
from bank_data.seed.runner import load_seed, plan_seed
from bank_data.seed.verify import verify_bundle

KEYS = IdentityKeys(b"seed-fixture-secret-" + b"s" * 32)
SLA_DAYS = {Country.MX: 45, Country.CO: 15, Country.AR: 30}
PHONES = {"CUS-A-0001": ("MX1234567", "+52 55 1111 2345"), "CUS-B-0002": ("CO7654321", "+57 300 222 6789")}
PERSONAS = """
version: 1
seed: fixture-seed
customers:
  - id: cre-mx-complete
    criterion: complete_credit_profile
    country: MX
    workflows: [credit, dispute]
    demonstrates: fixture persona
    seeded_case: true
    seeded_application: true
  - id: cre-co-no-income
    criterion: credit_profile_without_income
    country: CO
    workflows: [credit]
    demonstrates: fixture persona
staff:
  - {id: agent-demo-01, staff_id: agent-demo-01, role: agent, display_name: Demo agent}
coverage: {min_customers_per_country: 1, every_segment: false}
"""


def _gold(tmp_path: Path, data: ContractDataset) -> Path:
    gold = tmp_path / "gold"
    gold.mkdir()
    write_gold(gold, data)
    write_table(
        gold,
        "customers_serving",
        (
            (
                item.customer_id,
                item.first_name,
                item.country.value,
                item.segment.value,
                item.status.value,
                "CC",
                *PHONES[item.customer_id],
                SNAPSHOT,
            )
            for item in data.customers
        ),
    )
    return gold


async def _count(instance: PostgresInstance, table: str) -> int:
    connection = await asyncpg.connect(
        host=instance.host,
        port=instance.port,
        database=instance.database,
        user=instance.owner,
        password=instance.owner_password,
    )
    try:
        return int(await connection.fetchval(f"SELECT count(*) FROM app.{table}"))  # noqa: S608
    finally:
        await connection.close()


async def test_seeding_twice_loads_the_same_rows(migrated_postgres: PostgresInstance, tmp_path: Path) -> None:
    await reset_database(migrated_postgres)
    (tmp_path / "personas.yaml").write_text(PERSONAS, encoding="utf-8")
    personas = load_personas(tmp_path / "personas.yaml")
    data = contract_dataset()
    selection, bundle = plan_seed(
        _gold(tmp_path, data), personas, KEYS, target=2, snapshot=date(2026, 6, 17), dispute_sla_days=SLA_DAYS
    )
    assert selection.personas == {"cre-mx-complete": "CUS-A-0001", "cre-co-no-income": "CUS-B-0002"}
    assert all(entry.document_lookup != PHONES[entry.customer_id][0] for entry in bundle.identities)
    (case,) = bundle.cases
    assert (case.sla_due_at - case.opened_at).days == SLA_DAYS[Country.MX]

    counts = []
    for _ in range(2):
        engine = owner_engine(migrated_postgres)
        try:
            counts.append(await load_seed(engine, bundle, app_role=migrated_postgres.app_user))
            verified = await verify_bundle(engine, selection, bundle)
            assert verified.counts["customers"] == 2
            assert verified.counts["transactions"] == len(data.transactions)
            assert verified.personas == 2
        finally:
            await engine.dispose()
        tables = ("customers", "products", "transactions", "credit_profiles", "dispute_cases", "credit_applications")
        counts.append({table: await _count(migrated_postgres, table) for table in tables})
    assert counts[1] == counts[3]
    assert counts[1]["transactions"] == len(data.transactions)
    assert counts[1]["dispute_cases"] == 1
    assert counts[1]["credit_applications"] == 1
    assert await _count(migrated_postgres, "identity_directory") == 2
    assert await _count(migrated_postgres, "staff_members") == 1


async def test_verification_rejects_changed_identity_digest(
    migrated_postgres: PostgresInstance, tmp_path: Path
) -> None:
    await reset_database(migrated_postgres)
    (tmp_path / "personas.yaml").write_text(PERSONAS, encoding="utf-8")
    selection, bundle = plan_seed(
        _gold(tmp_path, contract_dataset()),
        load_personas(tmp_path / "personas.yaml"),
        KEYS,
        target=2,
        snapshot=date(2026, 6, 17),
        dispute_sla_days=SLA_DAYS,
    )
    engine = owner_engine(migrated_postgres)
    try:
        await load_seed(engine, bundle, app_role=migrated_postgres.app_user)
        async with open_transaction(engine, DatabaseRole.SEED) as connection:
            await connection.execute(
                text("UPDATE app.identity_directory SET document_lookup = :digest WHERE customer_id = :id"),
                {"digest": "0" * 64, "id": selection.customers[0]},
            )
        with pytest.raises(SeedVerificationError, match="keyed lookup differs"):
            await verify_bundle(engine, selection, bundle)
    finally:
        await engine.dispose()


def test_an_unmatched_persona_stops_the_seed(tmp_path: Path) -> None:
    from bank_data.errors import ConfigurationError

    (tmp_path / "personas.yaml").write_text(PERSONAS.replace("country: CO", "country: AR"), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="cre-co-no-income"):
        plan_seed(
            _gold(tmp_path, contract_dataset()),
            load_personas(tmp_path / "personas.yaml"),
            KEYS,
            target=2,
            snapshot=date(2026, 6, 17),
            dispute_sla_days=SLA_DAYS,
        )


def test_the_seed_takes_the_dispute_sla_from_the_policy_pack() -> None:
    from bank_agent.bootstrap.settings import load_settings
    from bank_data.seed.command import dispute_sla_days

    assert dispute_sla_days(load_settings(env_file=None)) == SLA_DAYS
