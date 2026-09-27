"""Dispute cases, credit application intakes, and the idempotency ledger of product writes.

Each aggregate stores its validated domain document as JSONB next to the scalar columns that queries,
constraints, and row-level security use; check constraints keep the two in agreement.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-27
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

IDEMPOTENCY_KEY = "'^[A-Za-z0-9_-]{16,128}$'"

UPGRADE = (
    f"""
        CREATE TABLE app.dispute_cases (
            case_id text PRIMARY KEY,
            customer_id text NOT NULL,
            transaction_id text NOT NULL,
            product_id text NOT NULL,
            reason text NOT NULL CHECK (reason IN ('unrecognized', 'duplicate', 'wrong_amount', 'not_received',
                'atm_cash_not_dispensed', 'subscription_cancelled', 'other')),
            status text NOT NULL CHECK (status IN ('opened', 'in_review', 'resolved', 'rejected', 'escalated')),
            opened_at timestamptz NOT NULL,
            idempotency_key text NOT NULL CHECK (idempotency_key ~ {IDEMPOTENCY_KEY}),
            version integer NOT NULL CHECK (version >= 0),
            document jsonb NOT NULL,
            CONSTRAINT dispute_cases_key_per_customer UNIQUE (customer_id, idempotency_key),
            CONSTRAINT dispute_cases_on_own_transaction FOREIGN KEY (transaction_id, customer_id)
                REFERENCES app.transactions (transaction_id, customer_id),
            CONSTRAINT dispute_cases_on_own_product FOREIGN KEY (product_id, customer_id)
                REFERENCES app.products (product_id, customer_id),
            CONSTRAINT dispute_cases_document_agrees CHECK (
                document ->> 'case_id' = case_id
                AND document ->> 'customer_id' = customer_id
                AND document ->> 'transaction_id' = transaction_id
                AND document ->> 'product_id' = product_id
                AND document ->> 'reason' = reason
                AND document ->> 'status' = status
                AND document ->> 'idempotency_key' = idempotency_key
                AND (document ->> 'version')::integer = version
            )
        )
    """,
    "CREATE INDEX dispute_cases_recent ON app.dispute_cases (customer_id, opened_at DESC, case_id)",
    "CREATE INDEX dispute_cases_by_transaction ON app.dispute_cases (customer_id, transaction_id)",
    f"""
        CREATE TABLE app.credit_applications (
            application_id text PRIMARY KEY,
            customer_id text NOT NULL REFERENCES app.customers (customer_id),
            product_code text NOT NULL CHECK (product_code ~ '^[A-Z][A-Z0-9_-]{{2,31}}$'),
            status text NOT NULL
                CONSTRAINT credit_applications_status_lifecycle
                CHECK (status IN ('submitted', 'under_human_review', 'withdrawn', 'closed')),
            requested_amount numeric(15, 2) NOT NULL CHECK (requested_amount > 0),
            currency text NOT NULL CHECK (currency IN ('MXN', 'COP', 'ARS', 'USD')),
            requested_term_months integer NOT NULL CHECK (requested_term_months BETWEEN 1 AND 480),
            created_at timestamptz NOT NULL,
            idempotency_key text NOT NULL CHECK (idempotency_key ~ {IDEMPOTENCY_KEY}),
            version integer NOT NULL CHECK (version >= 0),
            document jsonb NOT NULL,
            CONSTRAINT credit_applications_key_per_customer UNIQUE (customer_id, idempotency_key),
            CONSTRAINT credit_applications_document_agrees CHECK (
                document ->> 'application_id' = application_id
                AND document ->> 'customer_id' = customer_id
                AND document ->> 'product_code' = product_code
                AND document ->> 'status' = status
                AND document ->> 'idempotency_key' = idempotency_key
                AND (document ->> 'requested_term_months')::integer = requested_term_months
                AND (document ->> 'version')::integer = version
            )
        )
    """,
    "CREATE INDEX credit_applications_recent ON app.credit_applications (customer_id, created_at DESC, application_id)",
    f"""
        CREATE TABLE app.action_idempotency (
            customer_id text NOT NULL REFERENCES app.customers (customer_id),
            action text NOT NULL CHECK (action IN ('block_card')),
            idempotency_key text NOT NULL CHECK (idempotency_key ~ {IDEMPOTENCY_KEY}),
            target text NOT NULL,
            request_digest text NOT NULL CHECK (request_digest ~ '^[0-9a-f]{{64}}$'),
            outcome text NOT NULL CHECK (length(outcome) BETWEEN 1 AND 64),
            recorded_at timestamptz NOT NULL,
            PRIMARY KEY (customer_id, action, idempotency_key)
        )
    """,
)

DOWNGRADE = (
    "DROP TABLE app.action_idempotency",
    "DROP TABLE app.credit_applications",
    "DROP TABLE app.dispute_cases",
)


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE:
        op.execute(statement)
