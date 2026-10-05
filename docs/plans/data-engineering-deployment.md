# Data engineering deployment and connection

Updated: 2026-10-04. Owner: Julian Valencia. Scope: retain the existing dedicated data VM
`vm-bank-database` in `rg-bank-agent`, westus2, and private storage `stla70238253ae46a02964`
in `rg-la70-test`, eastus2. Organize repository code and documentation under `data-engineering`.
The operator cancelled Azure renaming; [ADR 0042](../adr/0042-preserve-azure-resource-names.md)
records the decision. [The process guide](../data/data-engineering-process.md) explains every stage.

## Implementation

- Add an ARM template for an Ubuntu VM, closed inbound networking, private artifact container, and
  managed identity access. Restrict writes to the dedicated data resources and the original artifact
  container; preserve the existing public application VM and unrelated workloads.
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

- The dedicated 2-vCPU VM already runs in westus2; no additional VM is requested. Eastus2 remains
  full; a Free Trial quota increase was rejected.
- Execute the full local source on the existing data VM, preserving the bounded PostgreSQL seed. The complete
  PostgreSQL batch loader remains a separate project. The public application is not rewired by this task.
- The VM and disks incur charges. Use 2 vCPU, 8 GiB RAM, and a 128 GiB Standard SSD; no hosted LLM.
- PostgreSQL on the VM avoids unverified managed-server bootstrap changes but requires backups.
- Existing uncommitted card fixes and local setup changes belong to the human and remain untouched.
