"""The language model budget ledger shared by every API process.

One row per counter: a session lineage (tokens), a conversation (USD), or a UTC day (USD). The keys are opaque ids and
dates; no customer data, prompt, or reply is stored, so the table has no row-level security. The application role may
read, insert, and update rows, never delete them.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-29
"""

import re

from alembic import context, op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def _app_role() -> str:
    role = str(context.config.attributes.get("app_role", "bank_app"))
    if re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", role) is None:
        raise ValueError("the application role name is not a plain identifier")
    return role


def upgrade() -> None:
    app = _app_role()
    op.execute("""
        CREATE TABLE app.llm_budget (
            scope text NOT NULL CHECK (scope IN ('session', 'conversation', 'day')),
            scope_key text NOT NULL CHECK (length(scope_key) BETWEEN 1 AND 64),
            tokens bigint NOT NULL DEFAULT 0 CHECK (tokens >= 0),
            cost_usd numeric(18, 8) NOT NULL DEFAULT 0 CHECK (cost_usd >= 0),
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (scope, scope_key)
        )
    """)
    op.execute(f'GRANT SELECT, INSERT, UPDATE ON app.llm_budget TO "{app}"')


def downgrade() -> None:
    op.execute("DROP TABLE app.llm_budget")
