# 0037: Production secrets in Azure Key Vault with workload identity

- Status: accepted
- Date: 2026-09-30
- Update (2026-10-04): renumbered from 0036, which `main` had already assigned to the Grafana live analytics record. Azure has since been selected for the event deployment (one VM, [ADR 0019](0019-single-host-compose-deployment.md)). Accepted with its implementation, pull request 27 (`feat/azure-key-vault-secrets`), which this record lands with; "Implementation" below records what the code does, including the one point where it departs from the first proposal (the env-file source kept for non-Azure hosts).

## Context

The service has production secrets for PostgreSQL, session signing, CSRF signing, and optionally hosted language-model or one-time-code providers. `bootstrap/settings.py` currently reads configuration from environment variables, wraps secret values in `SecretStr`, and refuses weak production secrets. `.env` is for local development and must not become the production secret store.

The planned phase 16 deployment uses Docker Compose and Caddy on a small host (`deploy/README.md`). A production secret source should provide access control and audit records, avoid storing credentials in the repository, images, or deployment commands, and support rotation. The cloud provider for the host has not yet been selected.

## Considered options

1. **Manually provisioned host environment file.** This is straightforward for one server, but creates another copy of each secret to protect, gives weak access auditing, and makes rotation a manual process. It is appropriate for local development, not the production source of truth.
2. **Azure Key Vault accessed through the host's managed identity.** Azure manages the identity credentials, and Key Vault provides centralized access control and audit logs. For Compose on an Azure VM, a host deployment service can retrieve secrets and stage them as protected files for Compose to mount only into the required containers. This keeps the existing deployment shape, but the VM remains a shared trust boundary and the deployment must refresh mounted files and restart affected services during rotation.
3. **Azure Container Apps with Key Vault references.** The platform can resolve Key Vault references using a managed identity and expose values to the app without a host-side fetch-and-stage script. This removes secret staging from the deployment host, but changes the planned Compose-and-Caddy deployment target and its operational model.

## Decision

Propose option 2 for the phase 16 Compose deployment, if the team selects Azure for the host. Azure Key Vault is the production source of truth; a managed identity is used to retrieve secrets, with no client secret or service-principal credential stored by the application.

- Grant the VM identity read access only to the dedicated application's required secrets. Do not grant secret write or delete access to the runtime identity.
- Retrieve values through a deployment or startup service, never in a shell command whose arguments or output are logged. Stage each value under a runtime-only directory such as `/run`, with host permissions that let only the intended non-root container identity read it. Treat access to the Docker daemon as root access. Do not write values to the checkout, persistent container volumes, or image layers.
- Use Compose secrets to mount each file read-only into only the service that needs it. The API receives its database application password, session and CSRF keys, and configured provider keys. The database owner credential is limited to database initialization or migration tasks; it is not supplied to the API.
- Extend the bootstrap settings source to read mounted secret files in production while keeping environment-based secrets for development and tests. Preserve `SecretStr` handling and the existing production validation. Secret values must not appear in logs, diagnostics, command-line arguments, or rendered Compose configuration.
- Document rotation as an operational procedure: publish a new Key Vault version, refresh the runtime files, restart the dependent service, and verify health without printing values. Rotate session and CSRF keys with the expected invalidation of existing sessions or tokens documented.
- If the host is Azure Container Apps instead, use its Key Vault references with managed identity. Do not add Kubernetes solely to obtain secret-manager integration.

## Consequences

- Production credentials have a central store, identity-based access, and an audit trail. Local development continues to use generated `.env` values and does not require Azure access.
- The Compose host and its administrators are trusted with every secret available to its VM identity. A compromised host can retrieve those secrets; this design does not provide per-container identities.
- Compose does not refresh an already-mounted secret automatically. Rotation depends on the deployment service refreshing files and restarting the affected containers, and needs an operational check.
- The settings layer reads mounted secret files (`SECRETS_DIR`); development and tests keep the environment and `.env`.
- The first proposal said a non-Azure host should not fall back to a persistent env file. The implementation keeps that fallback, deliberately and only as the documented weaker option: see "Implementation".

## Implementation

What pull request 27 built, so this record matches the code:

| Piece | What it does |
|---|---|
| `deploy/secrets_stage.py` | Standard-library Python run as root. Gets a token from the instance metadata service (no stored credential), reads each secret from the Key Vault REST API, follows no redirect, and writes `/run/bank-agent/secrets/{app,postgres,grafana}/<VARIABLE>` (a tmpfs) with mode 0400, owned by the container user (uid 10001, 70, 472), directories 0711. It reads every secret before writing any file, refuses a symbolic link or a relative destination, and prints names and HTTP statuses, never a value. A required secret that is missing or unreadable stops it; an optional one (the model keys, the Langfuse keys, the Grafana password) is staged empty. |
| `deploy/azure/bank-agent-secrets.service` | A systemd one-shot unit, ordered before Docker, that runs a root-owned copy of the stager at every boot (`deploy/azure/install-vm.sh` installs it). |
| `deploy/prod.sh` | `up` stages the secrets before validating and starting; `rotate` stages the current versions and recreates every service, because a running container keeps the file it started with; `check` verifies the staged files from their metadata only. With `SECRETS_SOURCE=keyvault` it refuses a secret value in the server env file. |
| `deploy/compose.prod.yml` | Compose secrets, one file per consumer: the API gets the application password, the session and CSRF keys, the model keys, and the Langfuse keys; the owner jobs get the owner password and the session key; PostgreSQL reads its three passwords through `*_FILE`; Grafana through `GF_SECURITY_ADMIN_PASSWORD__FILE`. No secret is an environment variable, so `docker inspect` and `docker compose config` show none. |
| `bootstrap/settings.py` | `SECRETS_DIR` adds pydantic's secret-file source to the database, security, model, and Langfuse settings. In production with `SECRETS_DIR`, a secret variable in the environment is refused (it would outrank the file), and every existing production rule (empty, short, known default, `dev-only-` placeholder, owner password in the API) applies to file values unchanged. |
| `deploy/azure/provision.sh`, `deploy/azure/keyvault-secrets.sh` | Create the vault (RBAC, soft delete 7 days), the VM with a system-assigned identity, and **Key Vault Secrets User for that identity on each application secret** (not on the vault); generate missing secrets without ever overwriting one, set provider keys typed at a hidden prompt, rotate the session, CSRF, and Grafana keys, and list names only. Values travel in mode 600 temporary files, never in arguments or output. |

The `env-file` source (`SECRETS_SOURCE=env-file`, the default) remains for the local production-stack test and for a non-Azure host: the values sit in the mode 600 server env file and are staged as the same files, so containers see no difference. It is weaker than Key Vault (a copy on disk, no audit), and `deploy/README.md` documents it that way.

Not covered: the one-time-code provider is a mock with no secret.

Update 2026-10-05: the Langfuse keys joined the same path. The stager stages `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` as optional `app` secrets (Key Vault `langfuse-public-key` and `langfuse-secret-key`, empty until they are set and granted), compose mounts them into the API only, and `prod.sh` refuses them in the env file with `SECRETS_SOURCE=keyvault`. `LANGFUSE_ENABLED` stays false by default. `prod.sh check`, which `up` and every release run after staging, refuses to start while a hosted model (`LLM_PROVIDER=litellm` with a model that needs a key) or an enabled Langfuse export has an empty staged key file, naming the file and never a value: an empty optional file is what an unset or ungranted secret produces, and the API would refuse its settings after the old containers were already replaced. The production procedure is in `deploy/README.md` ("Langfuse export"). Continuous deployment ([ADR 0038](0038-continuous-deployment-to-azure-with-github-actions.md)) adds no secret to the VM and no Key Vault access to its identity: it runs the same `prod.sh` commands, which stage the secrets with the VM identity.
