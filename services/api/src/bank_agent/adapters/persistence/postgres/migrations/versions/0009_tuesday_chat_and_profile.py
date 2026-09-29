"""Customer-wide assistant preferences and an ordered chat message timeline.

Turns remain workflow request/result records. Messages are independently ordered display entries, so a simulated
human can join and reply in the same conversation without pretending to be another customer turn.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-29
"""

import re

from alembic import context, op

revision = "0009"
down_revision = "0008"
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
        CREATE TABLE app.assistant_profiles (
            customer_id text PRIMARY KEY REFERENCES app.customers (customer_id),
            assistant_name text NOT NULL CHECK (
                length(assistant_name) BETWEEN 1 AND 40 AND assistant_name = btrim(assistant_name)
            ),
            avatar_key text NOT NULL CHECK (avatar_key ~ '^[a-z0-9][a-z0-9_-]{0,63}$'),
            updated_at timestamptz NOT NULL
        )
    """)
    op.execute("""
        ALTER TABLE app.turns ADD CONSTRAINT turns_message_owner_key
            UNIQUE (turn_id, conversation_id, customer_id)
    """)
    op.execute("""
        CREATE TABLE app.messages (
            message_id text PRIMARY KEY,
            conversation_id text NOT NULL,
            customer_id text NOT NULL,
            sequence integer NOT NULL CHECK (sequence > 0),
            sent_at timestamptz NOT NULL,
            role text NOT NULL CHECK (role IN ('user', 'assistant', 'mock_human', 'system')),
            text text NOT NULL CHECK (length(text) <= 4000),
            is_simulated boolean NOT NULL DEFAULT false,
            turn_id text,
            CONSTRAINT messages_sequence_per_conversation UNIQUE (conversation_id, sequence),
            CONSTRAINT messages_own_conversation FOREIGN KEY (conversation_id, customer_id)
                REFERENCES app.conversations (conversation_id, customer_id),
            CONSTRAINT messages_own_turn FOREIGN KEY (turn_id, conversation_id, customer_id)
                REFERENCES app.turns (turn_id, conversation_id, customer_id),
            CONSTRAINT messages_mock_is_simulated CHECK (role <> 'mock_human' OR is_simulated),
            CONSTRAINT messages_user_is_real CHECK (role <> 'user' OR NOT is_simulated)
        )
    """)
    op.execute(
        "CREATE INDEX messages_by_customer_conversation ON app.messages (customer_id, conversation_id, sequence)"
    )

    # A future production owner may not be a superuser. Temporarily remove FORCE so the table owner can read
    # existing turns without a customer context; restore it before this transactional migration commits.
    op.execute("ALTER TABLE app.turns NO FORCE ROW LEVEL SECURITY")
    op.execute("""
        INSERT INTO app.messages
            (message_id, conversation_id, customer_id, sequence, sent_at, role, text, is_simulated, turn_id)
        SELECT 'legacy-user-' || turn_id, conversation_id, customer_id, 2 * sequence - 1,
            received_at, 'user', document ->> 'customer_text', false, turn_id
        FROM app.turns
        UNION ALL
        SELECT 'legacy-assistant-' || turn_id, conversation_id, customer_id, 2 * sequence,
            COALESCE((document ->> 'completed_at')::timestamptz, received_at),
            'assistant', document -> 'response' ->> 'text', false, turn_id
        FROM app.turns
        WHERE document -> 'response' ->> 'text' IS NOT NULL
    """)
    op.execute("ALTER TABLE app.turns FORCE ROW LEVEL SECURITY")

    for table in ("assistant_profiles", "messages"):
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE app.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY customer_own ON app.{table} "
            "USING (app.ctx_role() = 'customer' AND customer_id = app.ctx_customer()) "
            "WITH CHECK (app.ctx_role() = 'customer' AND customer_id = app.ctx_customer())"
        )
    op.execute(f'REVOKE DELETE, TRUNCATE ON app.assistant_profiles FROM "{app}"')
    op.execute(f'REVOKE UPDATE, DELETE, TRUNCATE ON app.messages FROM "{app}"')
    op.execute("""
        CREATE TRIGGER messages_append_only BEFORE UPDATE OR DELETE ON app.messages
        FOR EACH ROW EXECUTE FUNCTION app.refuse_mutation()
    """)
    op.execute("""
        CREATE TRIGGER messages_no_truncate BEFORE TRUNCATE ON app.messages
        FOR EACH STATEMENT EXECUTE FUNCTION app.refuse_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TABLE app.messages")
    op.execute("ALTER TABLE app.turns DROP CONSTRAINT turns_message_owner_key")
    op.execute("DROP TABLE app.assistant_profiles")
