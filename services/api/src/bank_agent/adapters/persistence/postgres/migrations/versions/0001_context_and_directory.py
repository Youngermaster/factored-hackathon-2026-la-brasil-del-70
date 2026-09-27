"""Context helpers, customers, staff members, and the identity directory.

Revision ID: 0001
Revises:
Create Date: 2026-09-27
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


UPGRADE = (
    """
        CREATE FUNCTION app.ctx_role() RETURNS text LANGUAGE sql STABLE
        AS $$ SELECT nullif(current_setting('app.role', true), '') $$
    """,
    """
        CREATE FUNCTION app.ctx_customer() RETURNS text LANGUAGE sql STABLE
        AS $$ SELECT nullif(current_setting('app.customer_id', true), '') $$
    """,
    """
        CREATE FUNCTION app.refuse_mutation() RETURNS trigger LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'table %.% is append-only', TG_TABLE_SCHEMA, TG_TABLE_NAME
                USING ERRCODE = 'insufficient_privilege';
        END
        $$
    """,
    """
        CREATE TABLE app.customers (
            customer_id text PRIMARY KEY CHECK (customer_id ~ '^[A-Za-z0-9][A-Za-z0-9_-]{0,19}$'),
            country text NOT NULL CHECK (country IN ('MX', 'CO', 'AR')),
            segment text NOT NULL CHECK (segment IN ('premium', 'plus', 'basic', 'student')),
            status text NOT NULL CHECK (status IN ('active', 'inactive', 'suspended', 'closed')),
            first_name text NOT NULL CHECK (length(first_name) BETWEEN 1 AND 100),
            snapshot_date date
        )
    """,
    """
        CREATE TABLE app.staff_members (
            staff_id text PRIMARY KEY CHECK (staff_id ~ '^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$'),
            role text NOT NULL CHECK (role IN ('agent', 'evaluator')),
            persona_id text NOT NULL UNIQUE,
            display_name text NOT NULL CHECK (length(display_name) BETWEEN 1 AND 100)
        )
    """,
    """
        CREATE TABLE app.identity_directory (
            customer_id text PRIMARY KEY REFERENCES app.customers (customer_id),
            persona_id text UNIQUE,
            document_lookup text NOT NULL UNIQUE CHECK (document_lookup ~ '^[0-9a-f]{64}$'),
            phone_last4_lookup text NOT NULL CHECK (phone_last4_lookup ~ '^[0-9a-f]{64}$')
        )
    """,
)

DOWNGRADE = (
    "DROP TABLE app.identity_directory",
    "DROP TABLE app.staff_members",
    "DROP TABLE app.customers",
    "DROP FUNCTION app.refuse_mutation()",
    "DROP FUNCTION app.ctx_customer()",
    "DROP FUNCTION app.ctx_role()",
)


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE:
        op.execute(statement)
