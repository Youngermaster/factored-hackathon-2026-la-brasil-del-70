"""The committed sample through preparation, value reconciliation, and the real API smoke."""

import asyncio
import importlib.util
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bank_agent.adapters.identity.codes import IdentityKeys
from bank_agent.adapters.policy.filesystem import FilesystemPolicyRepository
from bank_agent.adapters.retrieval.index_store import build_index, write_index
from bank_agent.domain.locale import Country
from bank_agent_postgres import owner_engine, reset_database
from bank_agent_test_support import PostgresInstance
from bank_data import pipeline
from bank_data.seed.config import DEFAULT_SAMPLE_PERSONAS_FILE, load_personas
from bank_data.seed.runner import load_seed, plan_seed
from bank_data.seed.verify import verify_bundle
from bank_data.settings import REPOSITORY_ROOT, PipelineSettings
from bank_data.workspace import Workspace


def test_prepared_sample_supports_all_workflows_and_unchanged_ingestion(
    migrated_postgres: PostgresInstance, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = Workspace.resolve(
        "sample",
        pipeline=PipelineSettings(
            _env_file=None,
            bank_data_dir=tmp_path / "data",
            bank_data_duckdb_memory_limit="1GB",
            bank_data_duckdb_threads=2,
            bank_data_ingest_workers=2,
        ),
    )
    first = pipeline.ingest(workspace)
    assert first.exit_code == 0
    pipeline.build(workspace)
    pipeline.run_tests(workspace)
    secret = secrets.token_hex(48)
    selection, bundle = plan_seed(
        workspace.dbt_target().gold_dir,
        load_personas(DEFAULT_SAMPLE_PERSONAS_FILE),
        IdentityKeys(secret.encode()),
        target=200,
        snapshot=workspace.config.dataset.snapshot_date,
        dispute_sla_days={Country.MX: 45, Country.CO: 15, Country.AR: 30},
        seeded_at=datetime.now(UTC),
    )

    async def prepare() -> None:
        await reset_database(migrated_postgres)
        engine = owner_engine(migrated_postgres)
        try:
            await load_seed(engine, bundle, app_role=migrated_postgres.app_user)
            report = await verify_bundle(engine, selection, bundle, check_values=True)
            assert 12 <= report.counts["customers"] <= 200
        finally:
            await engine.dispose()

    asyncio.run(prepare())
    index_dir = tmp_path / "retrieval-index"
    write_index(build_index(FilesystemPolicyRepository.from_directory(REPOSITORY_ROOT / "policies")), index_dir)
    settings = {
        "APP_ENV": "production",
        "POSTGRES_HOST": migrated_postgres.host,
        "POSTGRES_PORT": str(migrated_postgres.port),
        "POSTGRES_DB": migrated_postgres.database,
        "POSTGRES_APP_USER": migrated_postgres.app_user,
        "POSTGRES_APP_PASSWORD": migrated_postgres.app_password,
        "SESSION_SECRET": secret,
        "CSRF_SECRET": secrets.token_hex(48),
        "CORS_ALLOWED_ORIGINS": "https://la70.internal",
        "DEMO_MODE": "true",
        "ALLOW_PUBLIC_DEMO_MODE": "true",
        "RATE_LIMIT_BACKEND": "postgres",
        "LLM_PROVIDER": "fake",
        "LLM_BUDGET_LEDGER": "postgres",
        "RETRIEVAL_INDEX_SOURCE": "stored",
        "RETRIEVAL_INDEX_DIR": str(index_dir),
    }
    for key, value in settings.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("POSTGRES_ADMIN_PASSWORD", raising=False)
    spec = importlib.util.spec_from_file_location(
        "data_engineering_smoke", REPOSITORY_ROOT / "deploy/data-engineering/smoke.py"
    )
    assert spec is not None
    assert spec.loader is not None
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    asyncio.run(smoke.run(tmp_path / "application.json"))
    evidence = json.loads((tmp_path / "application.json").read_text())
    assert len(evidence["flows"]) == 8
    assert evidence["cross_customer_status"] == 404
    second = pipeline.ingest(workspace)
    assert second.exit_code == 0
    assert second.counts()["loaded"] == 0
    assert second.unchanged == first.listed
