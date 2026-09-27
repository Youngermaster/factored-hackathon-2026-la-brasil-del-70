"""``bank-data seed``: select, map, migrate, and load, idempotently.

The database and the identity secret come from the service settings (``POSTGRES_*`` and ``SESSION_SECRET``),
read by ``bank_agent.bootstrap``; nothing here reads or prints a secret.
"""

import asyncio
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine

from bank_agent.adapters.identity.codes import IdentityKeys
from bank_agent.adapters.persistence.duckdb.gold import open_gold
from bank_agent.adapters.persistence.postgres import migrate
from bank_agent.adapters.persistence.postgres.seed import PostgresSeeder, SeedBundle
from bank_data.seed.bundle import build_bundle
from bank_data.seed.config import PersonaFile
from bank_data.seed.selection import Selection, select_customers


@dataclass(frozen=True)
class SeedReport:
    selection: Selection
    counts: dict[str, int]


def plan_seed(
    gold_dir: Path, personas: PersonaFile, keys: IdentityKeys, *, target: int, snapshot: date
) -> tuple[Selection, SeedBundle]:
    """Select customers and build the bundle, without touching PostgreSQL."""
    connection = open_gold(gold_dir)
    try:
        selection = select_customers(connection, personas, target=target, snapshot=snapshot)
        return selection, build_bundle(connection, personas, selection, keys, snapshot=snapshot)
    finally:
        connection.close()


async def load_seed(owner_engine: AsyncEngine, bundle: SeedBundle, *, app_role: str) -> dict[str, int]:
    """Bring the schema to head, then upsert the bundle. Running it twice leaves the same rows."""
    await migrate.upgrade(owner_engine, app_role=app_role)
    return (await PostgresSeeder(owner_engine).load(bundle)).counts


def run_seed(
    gold_dir: Path,
    personas: PersonaFile,
    keys: IdentityKeys,
    owner_engine: AsyncEngine,
    *,
    target: int,
    snapshot: date,
    app_role: str,
) -> SeedReport:
    selection, bundle = plan_seed(gold_dir, personas, keys, target=target, snapshot=snapshot)

    async def _load() -> dict[str, int]:
        try:
            return await load_seed(owner_engine, bundle, app_role=app_role)
        finally:
            await owner_engine.dispose()

    return SeedReport(selection=selection, counts=asyncio.run(_load()))
