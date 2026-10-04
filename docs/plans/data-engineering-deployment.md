# Data engineering deployment and connection

Updated: 2026-10-04. Owner: Julian Valencia. Scope: deploy and execute the existing data pipeline in
`vm-data-engineering-database` in `rg-data-engineering-test`, `westus2`, with private engineering storage
in the same region, then version its infrastructure and execution evidence. The operator approved
the naming and inspection scope in [ADR 0041](../adr/0041-data-engineering-deployment-and-datagrip.md).

## Implementation

- Prepare snapshots, a retained original disk, a database backup, and verified artifact copies before
  the explicitly approved replacement of the source VM. Verify recovery before retiring source resources.

- Add an ARM template for an Ubuntu VM, closed inbound networking, private artifact container, and
  managed identity access. Restrict writes to the dedicated data resources and the original artifact
  container; preserve the existing public application VM and Nequi.
- Add a deployment command that packages a committed revision, uploads it with Entra authentication,
  and uses VM Run Command. Never copy local secrets or the working tree's unrelated changes.
- Run ingestion, contracts, dbt build and freshness, quality and lineage reports, bounded seed,
  value reconciliation, and application workflow checks on the VM.
- Use the existing production roles and enable operator-authorized TLS inspection only from a single
  client IPv4 through [ADR 0041](../adr/0041-data-engineering-deployment-and-datagrip.md). Refuse automatic reseeding
  of an existing database. Preserve warehouses and publish content-addressed artifacts and evidence.
- Extend seed verification with an optional full reference-row comparison and corruption regressions.
- Record the deployment choice and measured execution in the deployment guide and progress log.

## Validation

- ARM deployment validation, shell syntax, lint, typing, and meaningful orchestration tests.
- PostgreSQL integration tests for value corruption and normal verification.
- VM execution evidence for all stages, four workflows, customer isolation, and an unchanged rerun.
- Run `make check` before completion; report unrelated existing failures without weakening checks.

## Risks and decisions

- Westus2 has capacity for the dedicated 2-vCPU VM, subject to current SKU validation. Eastus2 remains
  full; a Free Trial quota increase was rejected.
- Execute the full local source on the new VM, preserving the bounded PostgreSQL seed. The complete
  PostgreSQL batch loader remains a separate project. The public application is not rewired by this task.
- The VM and disks incur charges. Use 2 vCPU, 8 GiB RAM, and a 128 GiB Standard SSD; no hosted LLM.
- PostgreSQL on the VM avoids unverified managed-server bootstrap changes but requires backups.
- Existing uncommitted card fixes and local setup changes belong to the human and remain untouched.
