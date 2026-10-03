# Azure data pipeline execution

Date: 2026-10-03. Owner: Julian Valencia. Scope: deploy and execute the existing data pipeline in
`rg-la70-test`, `eastus2`, then version its infrastructure, application changes, and execution evidence.

## Implementation

- Add an ARM template for an Ubuntu VM, closed inbound networking, private artifact container, and
  managed identity access. Keep every resource in the authorized resource group.
- Add a deployment command that packages a committed revision, uploads it with Entra authentication,
  and uses VM Run Command. Never copy local secrets or the working tree's unrelated changes.
- Run ingestion, contracts, dbt build and freshness, quality and lineage reports, bounded seed,
  value reconciliation, and application workflow checks on the VM.
- Keep PostgreSQL private on the VM with the existing production roles. Refuse automatic reseeding
  of an existing database. Preserve warehouses and publish content-addressed artifacts and evidence.
- Extend seed verification with an optional full reference-row comparison and corruption regressions.
- Record the deployment choice and measured execution in the deployment guide and progress log.

## Validation

- ARM deployment validation, shell syntax, lint, typing, and meaningful orchestration tests.
- PostgreSQL integration tests for value corruption and normal verification.
- VM execution evidence for all stages, four workflows, customer isolation, and an unchanged rerun.
- Run `make check` before completion; report unrelated existing failures without weakening checks.

## Risks and decisions

- Regional CPU quota is currently exhausted; the human authorized requesting a rise from 4 to 6 vCPU.
- First execution uses the committed sample, explicitly labeled; local and S3 inputs retain their
  existing commands. Full organizer loading remains a separate batch-loader project.
- The VM and disks incur charges. Use 2 vCPU, 8 GiB RAM, and a 128 GiB Standard SSD; no hosted LLM.
- PostgreSQL on the VM avoids unverified managed-server bootstrap changes but requires backups.
- Existing uncommitted card fixes and local setup changes belong to the human and remain untouched.
