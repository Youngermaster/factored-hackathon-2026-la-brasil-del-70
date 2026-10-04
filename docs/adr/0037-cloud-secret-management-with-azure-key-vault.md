# 0037: Production secrets in Azure Key Vault with workload identity

- Status: proposed
- Date: 2026-09-30
- Update (2026-10-04): renumbered from 0036, which `main` had already assigned to the Grafana live analytics record. Azure has since been selected for the event deployment (one VM, [ADR 0019](0019-single-host-compose-deployment.md)); the implementation that stages the production secrets from Key Vault is pull request 27 (`feat/azure-key-vault-secrets`). This record stays proposed until that pull request is merged.

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
- The settings layer needs a production file-based secret source. Until that is implemented, the current environment-only settings do not fulfill this proposal.
- The ADR leaves the hosting provider open. If the team chooses a non-Azure host, select its equivalent managed secret store and workload identity before phase 16 deployment; do not fall back to a committed or persistent `.env` file.
