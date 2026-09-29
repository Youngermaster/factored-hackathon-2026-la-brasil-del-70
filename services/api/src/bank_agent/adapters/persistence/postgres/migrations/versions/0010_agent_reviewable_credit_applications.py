"""Agents read every reviewable credit application intake.

A submitted intake is a review item of its own (phase 02b, ADR 0021), so the agent read policy on
``app.credit_applications`` widens from "a handoff references it" to "its status is ``submitted`` or
``under_human_review``, or a handoff references it". Customers are unchanged; agents still cannot write.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-29
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

_REFERENCED = "EXISTS (SELECT 1 FROM app.handoffs h WHERE h.application_ref = credit_applications.application_id)"


def upgrade() -> None:
    op.execute("DROP POLICY agent_referenced ON app.credit_applications")
    op.execute(
        "CREATE POLICY agent_reviewable ON app.credit_applications FOR SELECT USING (app.ctx_role() = 'agent' "
        f"AND (status IN ('submitted', 'under_human_review') OR {_REFERENCED}))"
    )


def downgrade() -> None:
    op.execute("DROP POLICY agent_reviewable ON app.credit_applications")
    op.execute(
        "CREATE POLICY agent_referenced ON app.credit_applications FOR SELECT USING (app.ctx_role() = 'agent' "
        f"AND {_REFERENCED})"
    )
