"""Server-side sessions, one-time-code challenges, and the append-only trust events of each session lineage.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-27
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

HEX64 = "'^[0-9a-f]{64}$'"

UPGRADE = (
    f"""
        CREATE TABLE app.sessions (
            session_id text PRIMARY KEY,
            token_digest text NOT NULL UNIQUE CHECK (token_digest ~ {HEX64}),
            lineage_id text NOT NULL,
            role text NOT NULL CHECK (role IN ('customer', 'agent', 'evaluator')),
            customer_id text REFERENCES app.customers (customer_id),
            staff_id text REFERENCES app.staff_members (staff_id),
            auth_level text NOT NULL CHECK (auth_level IN ('none', 'identified', 'otp_verified')),
            created_at timestamptz NOT NULL,
            last_seen_at timestamptz NOT NULL,
            idle_timeout_seconds integer NOT NULL CHECK (idle_timeout_seconds > 0),
            absolute_expires_at timestamptz NOT NULL,
            step_up_expires_at timestamptz,
            revoked_at timestamptz,
            language_preference text CHECK (language_preference IN ('es', 'pt', 'en')),
            CONSTRAINT sessions_one_subject CHECK (
                (role = 'customer' AND customer_id IS NOT NULL AND staff_id IS NULL)
                OR (role <> 'customer' AND staff_id IS NOT NULL AND customer_id IS NULL)
            ),
            CONSTRAINT sessions_instants_in_order
                CHECK (last_seen_at >= created_at AND absolute_expires_at > created_at)
        )
    """,
    "CREATE INDEX sessions_by_lineage ON app.sessions (lineage_id, created_at)",
    f"""
        CREATE TABLE app.otp_challenges (
            challenge_id text PRIMARY KEY,
            purpose text NOT NULL CHECK (purpose IN ('login', 'step_up')),
            subject_key text NOT NULL CHECK (subject_key ~ {HEX64}),
            customer_id text REFERENCES app.customers (customer_id),
            staff_id text REFERENCES app.staff_members (staff_id),
            session_id text REFERENCES app.sessions (session_id),
            code_hash text NOT NULL CHECK (code_hash ~ {HEX64}),
            salt text NOT NULL CHECK (salt ~ '^[0-9a-f]{{32}}$'),
            attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
            max_attempts integer NOT NULL CHECK (max_attempts > 0),
            created_at timestamptz NOT NULL,
            expires_at timestamptz NOT NULL,
            consumed_at timestamptz,
            locked_until timestamptz,
            CONSTRAINT otp_attempts_bounded CHECK (attempts <= max_attempts),
            CONSTRAINT otp_expiry_after_creation CHECK (expires_at > created_at),
            CONSTRAINT otp_at_most_one_subject CHECK (customer_id IS NULL OR staff_id IS NULL),
            CONSTRAINT otp_step_up_names_a_session CHECK (purpose = 'login' OR session_id IS NOT NULL)
        )
    """,
    "CREATE INDEX otp_challenges_by_subject ON app.otp_challenges (subject_key, created_at DESC)",
    f"""
        CREATE TABLE app.trust_events (
            lineage_id text NOT NULL,
            sequence integer NOT NULL CHECK (sequence > 0),
            occurred_at timestamptz NOT NULL,
            content_digest text NOT NULL CHECK (content_digest ~ {HEX64}),
            document jsonb NOT NULL,
            PRIMARY KEY (lineage_id, sequence)
        )
    """,
)

DOWNGRADE = (
    "DROP TABLE app.trust_events",
    "DROP TABLE app.otp_challenges",
    "DROP TABLE app.sessions",
)


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE:
        op.execute(statement)
