# 0009: Row-level security as defense in depth behind tool-layer scoping

- Status: accepted
- Date: 2026-09-27

## Context

The brief requires customer isolation in the service or tool layer. Tools never accept a customer identifier (the session context supplies it), and every repository filters by the context customer. A single bug in one query, or a new repository written in a hurry, would still leak another customer's rows. PostgreSQL row-level security can filter again below the application, but the application role sets its own context, so the database cannot tell a legitimate context from a buggy one.

## Considered options

1. **Tool and repository scoping only.** Simple, but one missing `WHERE` clause is a cross-customer disclosure.
2. **Row-level security only**, with repositories trusting the database. Every query would depend on a setting the application itself writes; a context bug would then be silent.
3. **Both**: repositories filter explicitly, and forced row-level security filters again on every customer table, with least-privilege grants and database-level guards for the audit tables.

## Decision

Option 3:

- The application connects as `bank_app`: `NOBYPASSRLS`, owns nothing, and holds only the privileges the service needs (read-only reference tables, a column grant for product status, no deletes, no updates on append-only tables).
- Every table has row-level security enabled and forced. Customer policies compare `customer_id` with `current_setting('app.customer_id', true)` when `app.role = 'customer'`; agents, evaluators, and the identity service have separate, narrower policies; without a context every policy is false.
- The unit of work sets both settings with `set_config(..., true)` inside each transaction, before any other statement, so a context never leaks across pooled connections.
- The seed runs as the owner with an explicit `app.role = 'seed'` and policies scoped `TO` the owner role only.
- Evaluation runs use a separate `eval` schema and a NOLOGIN `bank_evaluator` role with no access to customer data tables.
- Tests prove each layer separately: the contract suites prove repository scoping on the memory backend (which has no database), and raw SQL tests prove the database refuses on its own.

## Consequences

- A repository bug that forgets its filter still returns only the context customer's rows; a context bug is caught by the repository filter.
- RLS cannot stop a compromised application process, which can set any context: it is defense in depth, not an authorization system. The tool layer remains the primary control.
- Policies add a little planning cost per query; indexes lead with `customer_id` so the extra predicate is free.
- A non-superuser owner in production (phase 16) is subject to forced RLS too; the seed policies and the audit replay check were written with that in mind.
- The audit replay check needed a narrow `SECURITY DEFINER` function, because PostgreSQL applies SELECT policies to an explicit `ON CONFLICT` arbiter and customers may not read audit events.
