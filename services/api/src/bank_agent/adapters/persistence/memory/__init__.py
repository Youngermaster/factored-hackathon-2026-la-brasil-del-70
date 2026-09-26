"""In-memory persistence adapters.

They implement every repository port with the same access rules, append-only rules, idempotency, and
optimistic concurrency the PostgreSQL adapters (phase 05) must provide, and they pass the same shared contract
suites. Tests, fixtures, and the evaluation harness use them; they keep nothing across process restarts.
"""
