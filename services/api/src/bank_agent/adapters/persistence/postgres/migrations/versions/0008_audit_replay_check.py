"""A narrow replay check for audit events.

Appending an audit event must be a no-op when the identical event is replayed and must fail when a different event
reuses the id, from contexts that may not read audit events (a customer, the identity service). PostgreSQL applies
SELECT policies to an explicit ``ON CONFLICT`` arbiter, so the check is a SECURITY DEFINER function that returns
only the stored content digest of one event id, never its document.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-27
"""

import re

from alembic import context, op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def _app_role() -> str:
    role = str(context.config.attributes.get("app_role", "bank_app"))
    if re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", role) is None:
        raise ValueError("the application role name is not a plain identifier")
    return role


def upgrade() -> None:
    op.execute("CREATE POLICY owner_replay_check ON app.audit_events FOR SELECT TO CURRENT_USER USING (true)")
    op.execute("""
        CREATE FUNCTION app.audit_event_digest(p_event_id text) RETURNS text
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, app
        AS $$ SELECT content_digest FROM app.audit_events WHERE event_id = p_event_id $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.audit_event_digest(text) FROM PUBLIC")
    op.execute(f'GRANT EXECUTE ON FUNCTION app.audit_event_digest(text) TO "{_app_role()}"')


def downgrade() -> None:
    op.execute("DROP FUNCTION app.audit_event_digest(text)")
    op.execute("DROP POLICY owner_replay_check ON app.audit_events")
