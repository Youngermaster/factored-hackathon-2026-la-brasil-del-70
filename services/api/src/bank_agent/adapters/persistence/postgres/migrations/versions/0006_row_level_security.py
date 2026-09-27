"""Row-level security on every table: forced, keyed on ``app.role`` and ``app.customer_id``.

The unit of work sets both settings with ``set_config(..., true)`` inside each transaction. With no context
both are null, so every policy is false and every query returns zero rows. Seed policies apply only to the
role that runs the migrations (the owner) and only when it sets ``app.role = 'seed'``.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-27
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

ALL_TABLES = (
    "customers",
    "staff_members",
    "identity_directory",
    "products",
    "transactions",
    "historical_complaints",
    "credit_profiles",
    "dispute_cases",
    "credit_applications",
    "action_idempotency",
    "sessions",
    "otp_challenges",
    "trust_events",
    "conversations",
    "turns",
    "execution_records",
    "handoffs",
    "audit_events",
)
CUSTOMER_TABLES = (
    "customers",
    "products",
    "transactions",
    "historical_complaints",
    "credit_profiles",
    "dispute_cases",
    "credit_applications",
    "action_idempotency",
    "conversations",
    "turns",
    "execution_records",
)
IDENTITY_TABLES = ("staff_members", "identity_directory", "sessions", "otp_challenges", "trust_events")
SEEDED_TABLES = (
    "customers",
    "staff_members",
    "identity_directory",
    "products",
    "transactions",
    "historical_complaints",
    "credit_profiles",
    "dispute_cases",
    "credit_applications",
)
OWN = "app.ctx_role() = 'customer' AND customer_id = app.ctx_customer()"


def _statements() -> list[str]:
    statements: list[str] = []
    for table in ALL_TABLES:
        statements.append(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        statements.append(f"ALTER TABLE app.{table} FORCE ROW LEVEL SECURITY")
    for table in CUSTOMER_TABLES:
        statements.append(f"CREATE POLICY customer_own ON app.{table} USING ({OWN}) WITH CHECK ({OWN})")
    for table in IDENTITY_TABLES:
        statements.append(
            f"CREATE POLICY identity_service ON app.{table} "
            "USING (app.ctx_role() = 'identity') WITH CHECK (app.ctx_role() = 'identity')"
        )
    for table in SEEDED_TABLES:
        statements.append(
            f"CREATE POLICY seed_load ON app.{table} TO CURRENT_USER "
            "USING (app.ctx_role() = 'seed') WITH CHECK (app.ctx_role() = 'seed')"
        )
    statements.extend(
        (
            f"CREATE POLICY customer_read ON app.handoffs FOR SELECT USING ({OWN})",
            f"CREATE POLICY customer_insert ON app.handoffs FOR INSERT WITH CHECK ({OWN})",
            "CREATE POLICY agent_read ON app.handoffs FOR SELECT USING (app.ctx_role() = 'agent')",
            "CREATE POLICY agent_lifecycle ON app.handoffs FOR UPDATE "
            "USING (app.ctx_role() = 'agent') WITH CHECK (app.ctx_role() = 'agent')",
            "CREATE POLICY evaluator_read ON app.handoffs FOR SELECT USING (app.ctx_role() = 'evaluator')",
            "CREATE POLICY agent_referenced ON app.dispute_cases FOR SELECT USING (app.ctx_role() = 'agent' "
            "AND EXISTS (SELECT 1 FROM app.handoffs h WHERE h.case_ref = dispute_cases.case_id))",
            "CREATE POLICY agent_referenced ON app.credit_applications FOR SELECT USING (app.ctx_role() = 'agent' "
            "AND EXISTS (SELECT 1 FROM app.handoffs h WHERE h.application_ref = credit_applications.application_id))",
            "CREATE POLICY evaluator_read ON app.execution_records FOR SELECT USING (app.ctx_role() = 'evaluator')",
            "CREATE POLICY evaluator_read ON app.audit_events FOR SELECT USING (app.ctx_role() = 'evaluator')",
            "CREATE POLICY context_append ON app.audit_events FOR INSERT WITH CHECK ("
            f"({OWN}) OR (app.ctx_role() IN ('agent', 'evaluator', 'identity') AND customer_id IS NULL))",
        )
    )
    return statements


def upgrade() -> None:
    for statement in _statements():
        op.execute(statement)


DROP_POLICIES = (
    "DO $$ DECLARE p record; BEGIN "
    "FOR p IN SELECT policyname FROM pg_policies WHERE schemaname = 'app' AND tablename = '{table}' LOOP "
    "EXECUTE format('DROP POLICY %I ON app.{table}', p.policyname); END LOOP; END $$"
)


def downgrade() -> None:
    for table in ALL_TABLES:
        op.execute(DROP_POLICIES.format(table=table))
        op.execute(f"ALTER TABLE app.{table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE app.{table} DISABLE ROW LEVEL SECURITY")
