# ADR 0038: execute the existing data pipeline on an Azure VM

- Status: Accepted
- Date: 2026-10-03
- Decision makers: Julian Valencia

## Context

The human approved executing and versioning the existing data pipeline in Azure, prioritizing quality over
quantity. Pandera contracts, quarantine, dbt-duckdb, deterministic selection, and PostgreSQL roles already
exist. The full local delivery needs persistent workspace storage. Automatic reseeding can reset card state.
The subscription's regional CPU quota is exhausted; provisioning must not modify other resource groups.

Remote branches already reserve 0036 for secret management and 0037 for dispute orchestration. This record
does not supersede either proposal or change the four-workflow scope.

## Considered options

1. **VM with the existing pipeline and private PostgreSQL.** Least adaptation, persistent workspace, and
   existing role bootstrap. The team must maintain the operating system, database, backups, and capacity.
2. **Container Apps Jobs with managed PostgreSQL.** Execution lifecycle and managed database operations,
   but requires storage design, compatible role/bootstrap operations, and measured resource sizing.
3. **Data Factory orchestration and copying.** Useful connectors and visual orchestration, but quality
   contracts, field ownership, and identity conversion still need the existing code or an integration layer.

## Decision

Choose option 1 for this execution. Use an ARM template restricted by the operator script to `rg-la70-test`
in `eastus2`, an Ubuntu 24.04 VM, closed inbound networking, production PostgreSQL roles, and a private Blob
artifact container accessed using Entra ID and the VM managed identity. Keep the initial customer slice at
up to 200. Package only a committed revision. First exercise the committed sample; retain existing local/S3 input
commands without sending source credentials through deployment commands.

Make value reconciliation mandatory for this runner. Refuse automatic reseeding when the database already
contains customers. Record code, source, dataset and snapshot versions, artifact hashes, stage results, and
application checks. Run all four workflows in Spanish and Portuguese against the actual database and test
customer isolation. Publish logs, gold, reports, and a backup privately.

## Consequences

- No public PostgreSQL, SSH, or API endpoint is needed. Run Command remains privileged administration.
- A changed source or application-owned product state makes strict reconciliation fail, rather than
  silently changing operational data. A continuous-refresh loader still needs a field-ownership policy.
- A sample run proves execution, not full-delivery capacity, learned-model accuracy, browser delivery,
  or a live-feed freshness SLA. All evidence must label that limitation.
- Persistent VM, disk, public IP, and storage charges must be managed. A restore rehearsal is required
  before claiming production recoverability.
- VM creation waits for sufficient regional quota and an available SKU; storage can be deployed separately.
- No hosted-model credentials, organizer credentials, tokens, or server environment files enter Git or
  execution artifacts.
