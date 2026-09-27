"""Conversations, turns, execution records, handoffs, and audit events.

Append-only tables carry a ``content_digest`` and a unique arbiter index on ``(id, content_digest)``: replaying
an identical document is a no-op, and a different document with the same id violates the primary key.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-27
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

HEX64 = "'^[0-9a-f]{64}$'"

UPGRADE = (
    """
        CREATE TABLE app.conversations (
            conversation_id text PRIMARY KEY,
            customer_id text NOT NULL REFERENCES app.customers (customer_id),
            lineage_id text NOT NULL,
            status text NOT NULL,
            created_at timestamptz NOT NULL,
            version integer NOT NULL CHECK (version >= 0),
            document jsonb NOT NULL,
            CONSTRAINT conversations_owner_key UNIQUE (conversation_id, customer_id),
            CONSTRAINT conversations_document_agrees CHECK (
                document ->> 'conversation_id' = conversation_id
                AND document ->> 'customer_id' = customer_id
                AND document ->> 'status' = status
                AND (document ->> 'version')::integer = version
            )
        )
    """,
    "CREATE INDEX conversations_by_customer ON app.conversations (customer_id, created_at DESC)",
    """
        CREATE TABLE app.turns (
            turn_id text PRIMARY KEY,
            conversation_id text NOT NULL,
            customer_id text NOT NULL,
            sequence integer NOT NULL CHECK (sequence > 0),
            received_at timestamptz NOT NULL,
            document jsonb NOT NULL,
            CONSTRAINT turns_sequence_per_conversation UNIQUE (conversation_id, sequence),
            CONSTRAINT turns_of_own_conversation FOREIGN KEY (conversation_id, customer_id)
                REFERENCES app.conversations (conversation_id, customer_id),
            CONSTRAINT turns_document_agrees CHECK (
                document ->> 'turn_id' = turn_id
                AND document ->> 'conversation_id' = conversation_id
                AND (document ->> 'sequence')::integer = sequence
            )
        )
    """,
    f"""
        CREATE TABLE app.execution_records (
            turn_id text PRIMARY KEY,
            conversation_id text NOT NULL,
            customer_id text REFERENCES app.customers (customer_id),
            recorded_at timestamptz NOT NULL,
            content_digest text NOT NULL CHECK (content_digest ~ {HEX64}),
            document jsonb NOT NULL,
            CONSTRAINT execution_records_replay_arbiter UNIQUE (turn_id, content_digest),
            CONSTRAINT execution_records_document_agrees CHECK (
                document ->> 'turn_id' = turn_id AND document ->> 'conversation_id' = conversation_id
            )
        )
    """,
    "CREATE INDEX execution_records_by_conversation ON app.execution_records (conversation_id, recorded_at, turn_id)",
    f"""
        CREATE TABLE app.handoffs (
            handoff_id text PRIMARY KEY,
            customer_id text NOT NULL REFERENCES app.customers (customer_id),
            case_ref text,
            application_ref text,
            status text NOT NULL CHECK (status IN ('open', 'claimed', 'resolved')),
            priority text NOT NULL CHECK (priority IN ('low', 'medium', 'high', 'critical')),
            reason_code text NOT NULL,
            language text NOT NULL CHECK (language IN ('es', 'pt')),
            sla_due timestamptz NOT NULL,
            content_digest text NOT NULL CHECK (content_digest ~ {HEX64}),
            document jsonb NOT NULL,
            lifecycle jsonb NOT NULL,
            CONSTRAINT handoffs_replay_arbiter UNIQUE (handoff_id, content_digest),
            CONSTRAINT handoffs_document_agrees CHECK (
                document ->> 'handoff_id' = handoff_id
                AND document ->> 'customer_ref' = customer_id
                AND lifecycle ->> 'status' = status
            )
        )
    """,
    "CREATE INDEX handoffs_inbox ON app.handoffs (status, sla_due, handoff_id)",
    "CREATE INDEX handoffs_by_case ON app.handoffs (case_ref) WHERE case_ref IS NOT NULL",
    "CREATE INDEX handoffs_by_application ON app.handoffs (application_ref) WHERE application_ref IS NOT NULL",
    "CREATE INDEX handoffs_by_customer ON app.handoffs (customer_id)",
    """
        CREATE FUNCTION app.keep_handoff_document() RETURNS trigger LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.document IS DISTINCT FROM OLD.document OR NEW.customer_id IS DISTINCT FROM OLD.customer_id
                OR NEW.content_digest IS DISTINCT FROM OLD.content_digest THEN
                RAISE EXCEPTION 'a handoff document never changes' USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END
        $$
    """,
    """
        CREATE TRIGGER handoffs_document_immutable BEFORE UPDATE ON app.handoffs
        FOR EACH ROW EXECUTE FUNCTION app.keep_handoff_document()
    """,
    f"""
        CREATE TABLE app.audit_events (
            event_id text PRIMARY KEY,
            occurred_at timestamptz NOT NULL,
            customer_id text REFERENCES app.customers (customer_id),
            actor_role text CHECK (actor_role IN ('customer', 'agent', 'evaluator')),
            action text NOT NULL,
            outcome text NOT NULL CHECK (outcome IN ('success', 'failure', 'denied')),
            content_digest text NOT NULL CHECK (content_digest ~ {HEX64}),
            document jsonb NOT NULL,
            CONSTRAINT audit_events_replay_arbiter UNIQUE (event_id, content_digest),
            CONSTRAINT audit_events_document_agrees CHECK (
                document ->> 'event_id' = event_id AND document ->> 'action' = action
                AND document ->> 'outcome' = outcome
            )
        )
    """,
    "CREATE INDEX audit_events_by_time ON app.audit_events (occurred_at, event_id)",
    "CREATE INDEX audit_events_by_action ON app.audit_events (action, occurred_at)",
)

DOWNGRADE = (
    "DROP TABLE app.audit_events",
    "DROP TABLE app.handoffs",
    "DROP FUNCTION app.keep_handoff_document()",
    "DROP TABLE app.execution_records",
    "DROP TABLE app.turns",
    "DROP TABLE app.conversations",
)


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE:
        op.execute(statement)
