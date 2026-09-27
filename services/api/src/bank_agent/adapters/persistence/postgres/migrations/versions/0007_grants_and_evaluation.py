"""Least-privilege grants for the application role, append-only triggers, and the isolated evaluation schema.

The application role (``app_role`` in the runner's config attributes, ``bank_app`` by default) received
SELECT, INSERT, UPDATE, and DELETE on every table through the default privileges of the role script. This
revision narrows that to what the service does. ``bank_evaluator`` is a NOLOGIN role for evaluation runs: it
owns nothing, cannot read customer data tables, and is the only role with access to schema ``eval``.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-27
"""

import re

from alembic import context, op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

EVALUATOR_ROLE = "bank_evaluator"
READ_ONLY = (
    "customers",
    "staff_members",
    "identity_directory",
    "transactions",
    "historical_complaints",
    "credit_profiles",
)
APPEND_ONLY = ("execution_records", "audit_events", "trust_events")
NO_DELETE = (
    "products",
    "dispute_cases",
    "credit_applications",
    "action_idempotency",
    "sessions",
    "otp_challenges",
    "conversations",
    "turns",
    "handoffs",
)
EVALUATOR_READS = ("execution_records", "audit_events", "handoffs")
CREATE_EVALUATOR_ROLE = (
    "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'bank_evaluator') THEN "
    "CREATE ROLE bank_evaluator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS; END IF; END $$"
)


def _app_role() -> str:
    role = str(context.config.attributes.get("app_role", "bank_app"))
    if re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", role) is None:
        raise ValueError("the application role name is not a plain identifier")
    return role


def upgrade() -> None:
    app = _app_role()
    for table in READ_ONLY:
        op.execute(f'REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON app.{table} FROM "{app}"')
    for table in APPEND_ONLY:
        op.execute(f'REVOKE UPDATE, DELETE, TRUNCATE ON app.{table} FROM "{app}"')
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON app.{table} "
            "FOR EACH ROW EXECUTE FUNCTION app.refuse_mutation()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON app.{table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION app.refuse_mutation()"
        )
    for table in NO_DELETE:
        op.execute(f'REVOKE DELETE, TRUNCATE ON app.{table} FROM "{app}"')
    op.execute(f'REVOKE INSERT, UPDATE ON app.products FROM "{app}"')
    op.execute(f'GRANT UPDATE (status, status_changed_at) ON app.products TO "{app}"')
    op.execute(CREATE_EVALUATOR_ROLE)
    op.execute("CREATE SCHEMA eval")
    op.execute(f'REVOKE ALL ON SCHEMA eval FROM PUBLIC, "{app}"')
    op.execute(f"GRANT USAGE ON SCHEMA eval, app TO {EVALUATOR_ROLE}")
    op.execute("""
        CREATE TABLE eval.evaluation_runs (
            run_id text PRIMARY KEY CHECK (run_id ~ '^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$'),
            started_at timestamptz NOT NULL,
            finished_at timestamptz,
            scenario_set_version text NOT NULL,
            git_sha text NOT NULL CHECK (git_sha ~ '^[0-9a-f]{7,40}$'),
            status text NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
            summary jsonb NOT NULL DEFAULT '{}'::jsonb,
            CONSTRAINT evaluation_runs_finish_after_start CHECK (finished_at IS NULL OR finished_at >= started_at)
        )
    """)
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON eval.evaluation_runs TO {EVALUATOR_ROLE}")
    for table in EVALUATOR_READS:
        op.execute(f"GRANT SELECT ON app.{table} TO {EVALUATOR_ROLE}")
        op.execute(f"CREATE POLICY evaluation_runs_read ON app.{table} FOR SELECT TO {EVALUATOR_ROLE} USING (true)")


def downgrade() -> None:
    app = _app_role()
    for table in EVALUATOR_READS:
        op.execute(f"DROP POLICY evaluation_runs_read ON app.{table}")
        op.execute(f"REVOKE SELECT ON app.{table} FROM {EVALUATOR_ROLE}")  # noqa: S608  # nosec B608
    op.execute("DROP SCHEMA eval CASCADE")
    op.execute(f"REVOKE USAGE ON SCHEMA app FROM {EVALUATOR_ROLE}")
    op.execute(f"DROP ROLE {EVALUATOR_ROLE}")
    op.execute(f'REVOKE UPDATE (status, status_changed_at) ON app.products FROM "{app}"')
    for table in APPEND_ONLY:
        op.execute(f"DROP TRIGGER {table}_no_truncate ON app.{table}")
        op.execute(f"DROP TRIGGER {table}_append_only ON app.{table}")
    for table in (*READ_ONLY, *APPEND_ONLY, *NO_DELETE):
        op.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON app.{table} TO "{app}"')
