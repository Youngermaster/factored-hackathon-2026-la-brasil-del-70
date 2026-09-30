"""Agents move reviewable credit application intakes: into human review, then closed.

An agent context may update an intake only while it is reviewable (``submitted`` or ``under_human_review``), and only
to ``under_human_review`` or ``closed``; the domain allows ``submitted`` to ``under_human_review`` and
``under_human_review`` to ``closed``. There is still no approved or declined status, and customers keep their single
move (withdrawal) through their own policy. Every move is audited by the agent inbox in the same transaction.

PostgreSQL checks the new row of an UPDATE against the SELECT policies too, so an agent may also read an intake it
closed after a review (``closed`` with an ``under_human_review`` step in its history). The repository still lists and
returns only reviewable intakes and those a handoff references; this policy only lets the close itself happen.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-29
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE POLICY agent_review ON app.credit_applications FOR UPDATE "
        "USING (app.ctx_role() = 'agent' AND status IN ('submitted', 'under_human_review')) "
        "WITH CHECK (app.ctx_role() = 'agent' AND status IN ('under_human_review', 'closed'))"
    )
    op.execute(
        "CREATE POLICY agent_reviewed ON app.credit_applications FOR SELECT "
        "USING (app.ctx_role() = 'agent' AND status = 'closed' "
        "AND document -> 'status_history' @> '[{\"to_status\": \"under_human_review\"}]'::jsonb)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY agent_reviewed ON app.credit_applications")
    op.execute("DROP POLICY agent_review ON app.credit_applications")
