# Production application connection to PostgreSQL

Updated: 2026-10-04. Owner: Julian Valencia.

## Which database and user the application uses

The backend connects to database `bank_agent` as `bank_app`. This role can perform the application's
permitted reads and writes, owns no tables, and has no superuser or RLS-bypass privilege.
Customer context is installed inside every transaction by the persistence adapter; callers do not
put customer identifiers into the connection string. The frontend calls the API over HTTPS and never
receives database credentials or connects directly to PostgreSQL.

| Component | Database role | Purpose |
|---|---|---|
| API workers | `bank_app` | Application operations, sessions, identity, audit, shared limits, and budgets |
| Migration and seed jobs | `bank_owner` | Schema ownership and controlled loading |
| Retention job | `bank_owner` | The deployed stack's retention job |
| DataGrip | `bank_datagrip` | Manual SELECT-only inspection of the reference slice |
| Local backup/restore job | `postgres` | Administrative dump/restore inside the database container |

Do not use `bank_datagrip` for the API: it has restricted grants and defaults to read-only transactions.
Do not supply `POSTGRES_ADMIN_PASSWORD` to the API: production configuration explicitly rejects it.
The existing application VM `vm-bank-agent` and data VM `vm-bank-database` currently have separate databases.
Documenting a connection does not switch the deployed application to the engineering database.

## Supported production stack: API and database in the same Compose project

`deploy/compose.prod.yml` configures the API and jobs to use the internal Docker service `postgres:5432`.
PostgreSQL has no published host port. Secrets come from Azure Key Vault through the VM managed identity
or, for the `env-file` source, from the protected production environment file. The deployment stages
service-specific secret files under `/run/bank-agent/secrets` and mounts them at `/run/secrets`.
The API receives only its application credentials; administrative jobs receive the owner credentials.

The API's effective non-secret connection settings are:

```text
APP_ENV=production
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=bank_agent
POSTGRES_APP_USER=bank_app
RATE_LIMIT_BACKEND=postgres
LLM_BUDGET_LEDGER=postgres
SECRETS_DIR=/run/secrets
```

Supply `POSTGRES_APP_PASSWORD` through its mounted secret file, using the password assigned
to this database's `bank_app` role. It must satisfy production secret validation, including the
32-character minimum. Also supply `SESSION_SECRET`, `CSRF_SECRET`, the stored retrieval index, trusted
browser origins, and the chosen model settings according to [the production deployment guide](../../deploy/README.md).
Keep the application role writable; application reads also create sessions and execution records.

For a new production installation, run on its server:

```bash
deploy/prod.sh init-env
# Configure the site, origins, model, and secret source privately before staging.
deploy/prod.sh stage-secrets
deploy/prod.sh check
deploy/prod.sh build
deploy/prod.sh up
```

After `init-env`, set the real site/origin and other required values privately in `deploy/.env.production`
before staging and `check`. For Azure Key Vault, follow the deployment guide to provision the vault
and initialize with `SECRETS_SOURCE=keyvault`; secret values stay out of the environment file.
The file must have mode 600. Do not print it, commit it, or copy its values into a chat.
`up` runs migrations before the API starts. Follow the deployment guide for the initial seed; an existing
engineering database must not be reset by the production demo seed.

`POSTGRES_HOST` and `POSTGRES_PORT` are hardcoded in the current production Compose service definitions.
Adding them to `deploy/.env.production` does not override those definitions. An API container's
`localhost` is that API container, not the PostgreSQL container or the Azure VM.

## Reusing the engineering database on its own VM

The engineering database remains on `vm-bank-database`, resource group `rg-bank-agent`, westus2.
A backend process running directly on that VM can use the host loopback connection that the pipeline's
real API smoke already exercises:

| Setting | Value |
|---|---|
| `POSTGRES_HOST` | `127.0.0.1` |
| `POSTGRES_PORT` | `5432` |
| `POSTGRES_DB` | `bank_agent` |
| `POSTGRES_APP_USER` | `bank_app` |
| `POSTGRES_APP_PASSWORD` | Existing engineering application-role secret, supplied privately on the VM |
| Retrieval source | `RETRIEVAL_INDEX_SOURCE=stored` |
| Retrieval directory | `/opt/la70-data/data/retrieval-index` |

Bootstrap generates `/opt/la70-data/api.env` with the engineering application credential and session/CSRF
settings. `/opt/la70-data/owner.env` is separate. A service supervisor can load the protected API file into
a non-root API process and add the stored-index settings; never load the owner file into that process.
The pipeline sets the index variables after building the index and validates the real composition root
against this database through ASGI. This proves database integration, not an already published web service.

A containerized API needs an explicitly configured shared Docker network or another intentional route
to this database. The stock production Compose creates a separate PostgreSQL service and volume; starting
it on the data VM does not make it reuse `la70-data_pgdata`. Changing a project name, volume, or database
container can start an empty database. Preserve the existing data volume and resolve the destination
before migration, seed, or startup.

## Application on another VM: private connection prerequisites

For a separate application host, target private routing to the data VM. Its current private IPv4 is
`10.70.1.4`, observed through Azure CLI on 2026-10-04; confirm it again before deployment and establish
stable private addressing or DNS. This is the destination to prepare, not a connection already enabled
by this work. The public `13.66.169.189:5432` endpoint is configured for the authorized DataGrip client.

A separate-host rollout needs these changes and validations:

1. Establish routing from the application host to the database, using the same VNet, VNet peering,
   or another approved private connection. Confirm non-overlapping address ranges and effective routes.
   [Azure VNet peering](https://learn.microsoft.com/en-us/azure/virtual-network/virtual-network-peering-overview)
   connects VNets over the private Azure backbone; NSGs still govern access.
2. Permit inbound TCP 5432 only from the actual application private source address or narrowly scoped
   application subnet in the database NSG and host firewall. Preserve the existing DataGrip rule and
   deny remaining ingress. Determine the source as seen by PostgreSQL, including any NAT.
3. Permit `bank_app` to database `bank_agent` from that source in `pg_hba.conf`, using `hostssl` and
   SCRAM-SHA-256. Check rule ordering and parsing, then reload deliberately. Do not reuse the DataGrip
   client rule or broaden access to every database user.
4. Provide a server certificate whose SAN covers the chosen private DNS name or private IP. Trust its
   CA on the application host, and enforce certificate-chain and hostname verification. The existing
   DataGrip certificate verifies the public IP; that verification does not establish a private-name match.
   Preserve DataGrip trust when managing certificates. [PostgreSQL TLS verification](https://www.postgresql.org/docs/16/libpq-ssl.html)
   documents the `verify-full` behavior for libpq clients such as `psql`.
5. Add explicit TLS/CA configuration for the API's SQLAlchemy/asyncpg connection in the bootstrap and
   engine wiring, with tests for trusted, untrusted, and mismatched certificates. The current
   `DatabaseSettings` exposes host, port, database, and roles/passwords only; it has no database TLS/CA
   settings. The engine currently supplies no explicit certificate-verifying SSL context. Do not assume
   that a `POSTGRES_SSLMODE` or `DATABASE_URL` environment variable is supported by this application.
6. Configure the API and the relevant migration/seed/purge jobs to use the same intended destination,
   with their separate roles and credentials. Adapt the hardcoded Compose host and dependency lifecycle
   deliberately; do not let a local empty `postgres` service or a random `init-env` password become the
   source of truth for the existing remote database. Migration jobs need the same verified network/TLS path.
7. Back up and verify schema compatibility before migration. Match application code to the deployed
   Alembic head, currently `0014`, and retain application-owned state. The existing serving slice contains
   200 customers, 559 products, and 6,119 transactions; full-source transformation is not a complete
   production PostgreSQL load.
8. Test from the actual application host/container and verify the application behaviors below before
   switching traffic. Keep the existing application's deployment unchanged until the cutover is explicit.

This section defines the required integration work. No peering, new ingress rule, certificate rotation,
remote API wiring, or production cutover was performed as part of this documentation change.

## Verify the connection and application behavior

Run `deploy/prod.sh check`, `deploy/prod.sh status`, and `deploy/prod.sh smoke` for the standard stack.
For another deployment topology, run the equivalent probes from its real network context. Check
`/health/ready`, not only `/health/live`: readiness checks the configured database and rejects a read-only
connection. Confirm production settings are active and a database check is present; without a configured
application password, development can fall back to memory.

Before serving users, verify:

- The authenticated database user is `bank_app`, the database is `bank_agent`, and the schema head
  matches the application. Check roles and schema without logging passwords or a credential-bearing URL.
- The API process has no owner credential and the intended application-role password works.
- A customer's permitted data is readable, another customer's resources return 404, and unscoped
  application-role queries return no customer rows. Do not disable forced RLS to make a probe pass.
- An authorized, idempotent write and its read-back work on a controlled test persona. A SELECT-only
  DataGrip check alone does not validate the application write path.
- Sessions, identity challenges, audit, shared rate limits, and the budget ledger persist in PostgreSQL.
- Two workers can operate against the intended database. Current API pools allow five connections plus
  five overflow connections per worker; two workers can use up to twenty, with jobs requiring additional
  capacity. Pool pre-ping is enabled. Do not apply DataGrip's five-connection limit to `bank_app`.
- A database outage yields failed readiness and the expected degradation behavior; the process can
  recover its database connections after service returns.

Rotate the application password in PostgreSQL and in the protected API configuration together, then
restart API workers to replace pooled connections. Keep session-secret rotation separate because it
invalidates sessions and changes identity lookup keys; see the deployment guide's rotation procedure.

See [the full data engineering process](data-engineering-process.md),
[the production deployment guide](../../deploy/README.md), and
[customer data isolation](../security/data-isolation.md) for related controls.
