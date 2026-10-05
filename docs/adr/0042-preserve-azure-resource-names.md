# ADR 0042: Keep Azure resource names and organize the repository by data engineering

- Status: Accepted
- Date: 2026-10-04
- Decision makers: Julian Valencia
- Supersedes: [ADR 0041](0041-data-engineering-deployment-and-datagrip.md), Azure naming replacement only

## Context

The operator wants consistent data engineering organization and a complete explanation of the pipeline.
The existing `vm-bank-database` is healthy and its DataGrip password is configured. Renaming the Azure VM
would require replacement, downtime, new connection settings, and recovery work under a full regional
vCPU quota. Preparatory copies were made, but the VM was never replaced. The operator explicitly decided
to retain existing Azure names and reference them from the repository.

## Considered options

1. Replace owned Azure resources to match repository naming. Improves cloud name consistency, but
   interrupts the database connection and creates unnecessary migration and recovery work.
2. Keep existing Azure identifiers and use `data-engineering` for repository organization. Preserves
   the working infrastructure and connection while requiring an explicit resource-reference table.

## Decision

Choose option 2. Keep `vm-bank-database` in `rg-bank-agent`, westus2, and private storage
`stla70238253ae46a02964` in `rg-la70-test`, eastus2. DataGrip remains at `13.66.169.189:5432`, database
`bank_agent`, user `bank_datagrip`, with Full Verification and the existing password and CA certificate.

Use `deploy/data-engineering`, engineering test names, `data/data-engineering` for ignored operational
state, and engineering document names. Retain persistent VM, Docker, and database storage identifiers.
Remove the abandoned VM naming replacement helper and its feature-specific tests; keep the backup
restore verifier and the inspection security tests. Deployment commands target existing resources and
ignore the abandoned replacement disk pointer.

The [process guide](../data/data-engineering-process.md) documents identity, infrastructure, private
source/release transfer, contracts, bronze/silver/gold, application-schema loading, reconciliation,
API checks, evidence, backups, DataGrip, and measured limitations. The existing deployment and TLS
choices in ADR 0041 remain valid; its proposed Azure replacement is cancelled.

## Consequences

- No VM replacement, quota increase, resource retirement, password change, or new endpoint is required.
- Repository organization and cloud identifiers are different by design and explicitly documented.
- Existing application resources and unrelated workloads remain outside the engineering deployment scope.
- Preparatory resources in `rg-data-engineering-test` remain unused. Their storage, disk, snapshot,
  and public-IP charges may continue; this decision does not authorize deleting them. They are not
  dependencies of the current pipeline or DataGrip connection.
- The complete source is transformed, but PostgreSQL retains the verified bounded serving slice.
  A full loader and managed scheduling remain separate work.
