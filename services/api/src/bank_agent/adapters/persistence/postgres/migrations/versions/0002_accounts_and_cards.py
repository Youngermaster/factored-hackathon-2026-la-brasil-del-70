"""Products (accounts, cards, loans), transactions, historical complaints, and credit profiles.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-27
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

CURRENCIES = "('MXN', 'COP', 'ARS', 'USD')"

UPGRADE = (
    f"""
        CREATE TABLE app.products (
            product_id text PRIMARY KEY,
            customer_id text NOT NULL REFERENCES app.customers (customer_id),
            product_type text NOT NULL CHECK (product_type IN ('checking_account', 'savings_account',
                'credit_card', 'debit_card', 'personal_loan', 'mortgage', 'investment', 'other')),
            status text NOT NULL CHECK (status IN ('active', 'blocked', 'closed', 'suspended')),
            number_last4 text NOT NULL CHECK (number_last4 ~ '^[0-9A-Z]{{4}}$'),
            currency text NOT NULL CHECK (currency IN {CURRENCIES}),
            current_balance numeric(15, 2),
            credit_limit numeric(15, 2) CHECK (credit_limit >= 0),
            annual_interest_rate numeric(5, 2) CHECK (annual_interest_rate >= 0),
            opened_on date,
            expires_on date,
            balance_as_of timestamptz,
            days_past_due integer CHECK (days_past_due >= 0),
            status_changed_at timestamptz,
            CONSTRAINT products_balance_has_instant CHECK (current_balance IS NULL OR balance_as_of IS NOT NULL),
            CONSTRAINT products_owner_key UNIQUE (product_id, customer_id)
        )
    """,
    "CREATE INDEX products_by_customer ON app.products (customer_id, product_id)",
    f"""
        CREATE TABLE app.transactions (
            transaction_id text PRIMARY KEY,
            customer_id text NOT NULL,
            product_id text NOT NULL,
            occurred_at timestamptz NOT NULL,
            transaction_type text NOT NULL CHECK (transaction_type IN ('deposit', 'withdrawal', 'transfer',
                'payment', 'purchase', 'adjustment')),
            category text CHECK (category IN ('food', 'transport', 'services', 'entertainment', 'health', 'other')),
            amount numeric(15, 2) NOT NULL,
            currency text NOT NULL CHECK (currency IN {CURRENCIES}),
            amount_usd numeric(15, 2),
            channel text NOT NULL CHECK (channel IN ('atm', 'branch', 'web', 'app', 'pos', 'transfer')),
            status text NOT NULL CHECK (status IN ('approved', 'declined', 'pending', 'reversed')),
            merchant_name text CHECK (length(merchant_name) <= 150),
            merchant_category text CHECK (length(merchant_category) <= 50),
            location_country text NOT NULL CHECK (location_country ~ '^[A-Z]{{2}}$'),
            location_city text CHECK (length(location_city) <= 100),
            fraud_label boolean NOT NULL,
            fraud_score numeric(5, 2) CHECK (fraud_score BETWEEN 0 AND 100),
            CONSTRAINT transactions_on_own_product FOREIGN KEY (product_id, customer_id)
                REFERENCES app.products (product_id, customer_id),
            CONSTRAINT transactions_owner_key UNIQUE (transaction_id, customer_id)
        )
    """,
    "CREATE INDEX transactions_recent ON app.transactions (customer_id, occurred_at DESC, transaction_id)",
    "CREATE INDEX transactions_by_product ON app.transactions (customer_id, product_id, occurred_at DESC)",
    "CREATE INDEX transactions_by_type ON app.transactions (customer_id, transaction_type, occurred_at DESC)",
    f"""
        CREATE TABLE app.historical_complaints (
            complaint_id text PRIMARY KEY,
            customer_id text NOT NULL REFERENCES app.customers (customer_id),
            created_at timestamptz NOT NULL,
            case_type text NOT NULL CHECK (case_type IN ('complaint', 'claim', 'request', 'suggestion')),
            category text NOT NULL CHECK (length(category) BETWEEN 1 AND 100),
            subcategory text CHECK (length(subcategory) BETWEEN 1 AND 100),
            reception_channel text NOT NULL CHECK (reception_channel IN ('call_center', 'email', 'web', 'app',
                'branch', 'regulator')),
            affected_product_id text,
            claimed_amount numeric(15, 2),
            currency text CHECK (currency IN {CURRENCIES}),
            priority text NOT NULL CHECK (priority IN ('low', 'medium', 'high', 'critical')),
            CONSTRAINT complaints_amount_has_currency CHECK (claimed_amount IS NULL OR currency IS NOT NULL)
        )
    """,
    "CREATE INDEX complaints_recent ON app.historical_complaints (customer_id, created_at DESC, complaint_id)",
    f"""
        CREATE TABLE app.credit_profiles (
            customer_id text PRIMARY KEY REFERENCES app.customers (customer_id),
            credit_score integer,
            estimated_monthly_income numeric(12, 2),
            income_currency text CHECK (income_currency IN {CURRENCIES}),
            tenure_months integer CHECK (tenure_months >= 0),
            credit_product_count integer CHECK (credit_product_count >= 0),
            max_days_past_due integer CHECK (max_days_past_due >= 0),
            total_credit_limit numeric(20, 2),
            total_credit_limit_currency text CHECK (total_credit_limit_currency IN {CURRENCIES}),
            utilization numeric(12, 4) CHECK (utilization >= 0),
            as_of date NOT NULL,
            CONSTRAINT credit_income_has_currency
                CHECK (estimated_monthly_income IS NULL OR income_currency IS NOT NULL),
            CONSTRAINT credit_limit_has_currency
                CHECK (total_credit_limit IS NULL OR total_credit_limit_currency IS NOT NULL)
        )
    """,
)

DOWNGRADE = (
    "DROP TABLE app.credit_profiles",
    "DROP TABLE app.historical_complaints",
    "DROP TABLE app.transactions",
    "DROP TABLE app.products",
)


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE:
        op.execute(statement)
