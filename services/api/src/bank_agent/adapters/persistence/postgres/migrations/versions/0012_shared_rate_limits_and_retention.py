"""Shared rate-limit windows and the retention purge context.

``app.rate_limit_windows`` holds one counter per key digest and one-minute window, shared by every API process. The
keys are HMAC digests of a client address or a session token (never the raw value), so, like ``app.llm_budget``, the
table has no row-level security. The application role may read, insert, and update rows, never delete them.

The retention purge (``bank-agent retention purge``) runs as the owner in the ``retention`` context. Delete and read
policies for that context, bound to the owner (``TO CURRENT_USER``), cover exactly the tables the purge empties; the
append-only triggers on ``messages`` and ``trust_events`` allow a delete in that context and refuse every other
update or delete, as before. The application role still has no DELETE grant on any of these tables.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-29
"""

import re

from alembic import context, op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

PURGED_TABLES = (
    "messages",
    "turns",
    "conversations",
    "otp_challenges",
    "sessions",
    "trust_events",
    "credit_applications",
)
APPEND_ONLY_PURGED = ("messages", "trust_events")
RETENTION = "app.ctx_role() = 'retention'"


def _app_role() -> str:
    role = str(context.config.attributes.get("app_role", "bank_app"))
    if re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", role) is None:
        raise ValueError("the application role name is not a plain identifier")
    return role


def upgrade() -> None:
    app = _app_role()
    op.execute("""
        CREATE TABLE app.rate_limit_windows (
            key_digest text NOT NULL CHECK (key_digest ~ '^[0-9a-f]{64}$'),
            window_start timestamptz NOT NULL,
            hits integer NOT NULL CHECK (hits > 0),
            PRIMARY KEY (key_digest, window_start)
        )
    """)
    op.execute("CREATE INDEX rate_limit_windows_by_start ON app.rate_limit_windows (window_start)")
    op.execute(f'GRANT SELECT, INSERT, UPDATE ON app.rate_limit_windows TO "{app}"')
    op.execute(f'REVOKE DELETE, TRUNCATE ON app.rate_limit_windows FROM "{app}"')
    op.execute("""
        CREATE FUNCTION app.refuse_mutation_outside_retention() RETURNS trigger LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' AND app.ctx_role() = 'retention' THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'table %.% is append-only', TG_TABLE_SCHEMA, TG_TABLE_NAME
                USING ERRCODE = 'insufficient_privilege';
        END
        $$
    """)
    for table in APPEND_ONLY_PURGED:
        op.execute(f"DROP TRIGGER {table}_append_only ON app.{table}")
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON app.{table} "
            "FOR EACH ROW EXECUTE FUNCTION app.refuse_mutation_outside_retention()"
        )
    for table in PURGED_TABLES:
        op.execute(f"CREATE POLICY retention_read ON app.{table} FOR SELECT TO CURRENT_USER USING ({RETENTION})")
        op.execute(f"CREATE POLICY retention_delete ON app.{table} FOR DELETE TO CURRENT_USER USING ({RETENTION})")


def downgrade() -> None:
    for table in PURGED_TABLES:
        op.execute(f"DROP POLICY retention_delete ON app.{table}")
        op.execute(f"DROP POLICY retention_read ON app.{table}")
    for table in APPEND_ONLY_PURGED:
        op.execute(f"DROP TRIGGER {table}_append_only ON app.{table}")
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON app.{table} "
            "FOR EACH ROW EXECUTE FUNCTION app.refuse_mutation()"
        )
    op.execute("DROP FUNCTION app.refuse_mutation_outside_retention()")
    op.execute("DROP TABLE app.rate_limit_windows")
