-- Operational inspection access, separate from application and migration credentials.
BEGIN;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bank_datagrip') THEN
        CREATE ROLE bank_datagrip NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS NOINHERIT CONNECTION LIMIT 5;
    END IF;
END $$;
ALTER ROLE bank_datagrip NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
ALTER ROLE bank_datagrip SET default_transaction_read_only = on;
ALTER ROLE bank_datagrip SET statement_timeout = '30s';
ALTER ROLE bank_datagrip SET idle_in_transaction_session_timeout = '2min';
GRANT CONNECT ON DATABASE bank_agent TO bank_datagrip;
GRANT USAGE ON SCHEMA app TO bank_datagrip;
GRANT SELECT ON app.customers, app.products, app.transactions,
    app.historical_complaints, app.credit_profiles, app.alembic_version TO bank_datagrip;
DO $$ DECLARE tab text; BEGIN
    FOREACH tab IN ARRAY ARRAY['customers', 'products', 'transactions', 'historical_complaints', 'credit_profiles']
    LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'app'
                       AND tablename = tab AND policyname = 'datagrip_read') THEN
            EXECUTE format('CREATE POLICY datagrip_read ON app.%I FOR SELECT TO bank_datagrip USING (true)', tab);
        END IF;
    END LOOP;
END $$;
COMMIT;
