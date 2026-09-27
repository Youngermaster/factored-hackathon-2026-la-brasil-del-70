"""Glue for ``bank-data seed``: resolve the gold directory and the service settings, then run the seed."""

from pathlib import Path

from bank_agent.adapters.identity.codes import IdentityKeys
from bank_agent.adapters.persistence.postgres.database import create_engine
from bank_agent.bootstrap.persistence import owner_database_url
from bank_agent.bootstrap.settings import AppSettings, load_settings
from bank_data.errors import ConfigurationError
from bank_data.seed.config import DEFAULT_PERSONAS_FILE, load_personas
from bank_data.seed.runner import SeedReport, run_seed
from bank_data.workspace import Workspace

DEFAULT_SEED_CUSTOMERS = 200


def _checked(settings: AppSettings) -> tuple[bytes, str]:
    """The identity secret and the application role name; names every missing variable, never a value."""
    admin = settings.database.admin_password
    session_secret = settings.security.session_secret
    admin_value = admin.get_secret_value().strip() if admin is not None else ""
    secret_value = session_secret.get_secret_value().strip() if session_secret is not None else ""
    missing = [
        name
        for name, value in (("POSTGRES_ADMIN_PASSWORD", admin_value), ("SESSION_SECRET", secret_value))
        if not value
    ]
    if missing:
        raise ConfigurationError(f"set {', '.join(missing)} before seeding (see .env.example)")
    raw = session_secret.get_secret_value() if session_secret is not None else ""
    return raw.encode("utf-8"), settings.database.app_user  # the same bytes the service derives its keys from


def seed(
    workspace: Workspace,
    *,
    customers: int = DEFAULT_SEED_CUSTOMERS,
    personas_file: Path = DEFAULT_PERSONAS_FILE,
    settings: AppSettings | None = None,
) -> SeedReport:
    gold_dir = workspace.dbt_target().gold_dir
    if not (gold_dir / "customers_serving.parquet").is_file():
        raise ConfigurationError(f"no gold tables for the {workspace.source_kind} source; run make pipeline first")
    service = settings or load_settings()
    secret, app_role = _checked(service)
    try:
        keys = IdentityKeys(secret)
    except ValueError as error:
        raise ConfigurationError("SESSION_SECRET must be at least 32 bytes long") from error
    return run_seed(
        gold_dir,
        load_personas(personas_file),
        keys,
        create_engine(owner_database_url(service.database), pooled=False),
        target=customers,
        snapshot=workspace.config.dataset.snapshot_date,
        app_role=app_role,
    )
