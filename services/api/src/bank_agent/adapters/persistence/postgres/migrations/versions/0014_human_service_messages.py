"""Claim-scoped human exchanges attached to existing conversations, with forced RLS and retention.

Revision ID: 0014
Revises: 0013
"""

import re

from alembic import context, op

revision = "0014"
down_revision = "0013"
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
        CREATE TABLE app.human_messages (
            message_id text PRIMARY KEY CHECK (message_id ~ '^[A-Za-z0-9_-]{1,64}$'),
            handoff_id text NOT NULL REFERENCES app.handoffs (handoff_id),
            conversation_id text NOT NULL,
            customer_id text NOT NULL,
            sequence integer NOT NULL CHECK (sequence > 0),
            sent_at timestamptz NOT NULL,
            role text NOT NULL CHECK (role IN ('user', 'agent')),
            text text NOT NULL CHECK (length(text) BETWEEN 1 AND 4000),
            staff_id text,
            UNIQUE (handoff_id, sequence),
            FOREIGN KEY (conversation_id, customer_id)
                REFERENCES app.conversations (conversation_id, customer_id),
            CHECK ((role = 'user' AND staff_id IS NULL) OR (role = 'agent' AND staff_id IS NOT NULL))
        )
    """)
    op.execute("CREATE INDEX human_messages_by_conversation ON app.human_messages (conversation_id, sent_at)")
    op.execute("ALTER TABLE app.human_messages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE app.human_messages FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY customer_read ON app.human_messages FOR SELECT USING (
            app.ctx_role() = 'customer' AND customer_id = app.ctx_customer()
        )
    """)
    op.execute("""
        CREATE POLICY claimed_agent_read ON app.human_messages FOR SELECT USING (
            app.ctx_role() = 'agent' AND EXISTS (
                SELECT 1 FROM app.handoffs h WHERE h.handoff_id = human_messages.handoff_id
                AND h.lifecycle ->> 'claimed_by' = current_setting('app.staff_id', true)
            )
        )
    """)
    op.execute("""
        CREATE POLICY authorized_insert ON app.human_messages FOR INSERT WITH CHECK (
            EXISTS (
                SELECT 1 FROM app.handoffs h WHERE h.handoff_id = human_messages.handoff_id
                AND h.customer_id = human_messages.customer_id
                AND h.document ->> 'conversation_ref' = human_messages.conversation_id
                AND ((app.ctx_role() = 'customer' AND human_messages.role = 'user'
                      AND human_messages.customer_id = app.ctx_customer() AND h.status IN ('open', 'claimed'))
                     OR (app.ctx_role() = 'agent' AND human_messages.role = 'agent' AND h.status = 'claimed'
                         AND human_messages.staff_id = current_setting('app.staff_id', true)
                         AND h.lifecycle ->> 'claimed_by' = current_setting('app.staff_id', true)))
            )
        )
    """)
    for operation in ("SELECT", "DELETE"):
        op.execute(
            f"CREATE POLICY retention_{operation.lower()} ON app.human_messages FOR {operation} "
            "TO CURRENT_USER USING (app.ctx_role() = 'retention')"
        )
    op.execute(f'REVOKE ALL ON app.human_messages FROM "{app}"')
    op.execute(f'GRANT SELECT, INSERT ON app.human_messages TO "{app}"')
    op.execute(
        "CREATE TRIGGER human_messages_append_only BEFORE UPDATE OR DELETE ON app.human_messages "
        "FOR EACH ROW EXECUTE FUNCTION app.refuse_mutation_outside_retention()"
    )
    op.execute(
        "CREATE TRIGGER human_messages_no_truncate BEFORE TRUNCATE ON app.human_messages "
        "FOR EACH STATEMENT EXECUTE FUNCTION app.refuse_mutation()"
    )

    # Only the owner executing this trigger can close the conversation; agents gain no transcript access.
    op.execute("""
            CREATE POLICY human_close_owner_select ON app.conversations FOR SELECT
            TO CURRENT_USER USING (
                app.ctx_role() = 'agent' AND EXISTS (
                    SELECT 1 FROM app.handoffs h
                    WHERE h.document ->> 'conversation_ref' = conversations.conversation_id
                    AND h.customer_id = conversations.customer_id AND h.status = 'resolved'
                    AND h.lifecycle ->> 'claimed_by' = current_setting('app.staff_id', true)
                )
            )
    """)
    op.execute("""
            CREATE POLICY human_close_owner_update ON app.conversations FOR UPDATE
            TO CURRENT_USER USING (
                app.ctx_role() = 'agent' AND EXISTS (
                    SELECT 1 FROM app.handoffs h
                    WHERE h.document ->> 'conversation_ref' = conversations.conversation_id
                    AND h.customer_id = conversations.customer_id AND h.status = 'resolved'
                    AND h.lifecycle ->> 'claimed_by' = current_setting('app.staff_id', true)
                )
            )
    """)
    op.execute("""
        CREATE FUNCTION app.close_human_conversation() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
        BEGIN
            IF NEW.status = 'resolved' AND OLD.status = 'claimed' THEN
                IF app.ctx_role() <> 'agent' OR
                    OLD.lifecycle ->> 'claimed_by' IS DISTINCT FROM current_setting('app.staff_id', true) THEN
                    RAISE EXCEPTION 'only the assigned agent can close the conversation'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
                UPDATE app.conversations SET status = 'closed', version = version + 1,
                    document = document || jsonb_build_object(
                        'status', 'closed', 'version', version + 1,
                        'updated_at', NEW.lifecycle #> '{resolution,resolved_at}')
                    WHERE conversation_id = NEW.document ->> 'conversation_ref'
                    AND customer_id = NEW.customer_id;
            END IF;
            RETURN NEW;
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.close_human_conversation() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER handoffs_close_conversation AFTER UPDATE OF status ON app.handoffs "
        "FOR EACH ROW EXECUTE FUNCTION app.close_human_conversation()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER handoffs_close_conversation ON app.handoffs")
    op.execute("DROP FUNCTION app.close_human_conversation()")
    op.execute("DROP POLICY human_close_owner_update ON app.conversations")
    op.execute("DROP POLICY human_close_owner_select ON app.conversations")
    op.execute("DROP TABLE app.human_messages")
