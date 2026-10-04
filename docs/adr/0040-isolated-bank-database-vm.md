# ADR 0040: isolate the data pipeline on vm-bank-database in westus2

- Status: Accepted
- Date: 2026-10-04
- Decision makers: Julian Valencia
- Supersedes: [ADR 0039](0039-azure-vm-data-pipeline.md), deployment scope and first source only

## Context

The operator confirmed that `rg-bank-agent` belongs to this project and requested a separate VM named
`vm-bank-database` when the existing `vm-bank-agent` was found to have been created by another operator.
The existing VM already runs the public application and its own PostgreSQL. Its workloads must remain
untouched. Nequi remains outside scope. Eastus2 uses all four regional vCPU; westus2 has two of four
allocated, leaving capacity for the separate two-vCPU data VM.

The full contracted local source and gold tables are already stored privately in the original Blob
account in `rg-la70-test`, eastus2. Recreating those artifacts is unnecessary. Updated main uses ADR
0038 for Azure continuous deployment, so the unmerged data-pipeline record was renumbered to 0039.

## Considered options

1. **Run on the existing application VM.** Reuses capacity and a database, but competes with live API
   workloads and couples data-engineering changes to another operator's deployment and state.
2. **Create a dedicated vm-bank-database in westus2.** Fits the available quota, follows the requested
   naming, and isolates CPU, disk, PostgreSQL, and releases. Adds VM/network/disk costs and cross-region
   Blob transfer. Burstable CPU can slow sustained transformations when credits are depleted.
3. **Wait for an eastus2 quota increase.** Keeps compute near the existing Blob account but requires
   upgrading the Free Trial offer and obtaining more quota; neither condition is currently satisfied.

## Decision

Choose option 2, as instructed by the operator. Deploy `vm-bank-database` and dedicated network resources
under `rg-bank-agent`, westus2, using `Standard_B2as_v2` (2 vCPU, 8 GiB RAM), Ubuntu 24.04, a 128 GiB
Standard SSD, Trusted Launch, managed identity, and denied inbound traffic. The deployment script checks
the authorized operator, tenant, subscription, and both resource-group locations. Its compute template
contains neither `vm-bank-agent` nor Nequi resources.

Reuse the existing private `artifacts` container in eastus2. Give only the new VM identity contributor
access at that container's scope. Package committed code and use the already verified full source archive.
The first cloud data run uses the full local source: restore, contracts and quarantine, bronze, dbt silver
and gold, tests/freshness, quality/lineage, private PostgreSQL roles and migrations, the bounded seed,
value reconciliation, all four workflow checks in Spanish and Portuguese, and a backup. Repeat the run
without replacing source, database, or application-owned state, and publish the evidence privately.

## Consequences

- The current eastus2 quota no longer blocks this authorized deployment; actual SKU validation remains
  necessary and does not reserve capacity.
- All full-source transformations run in Azure. PostgreSQL retains ADR 0034's bounded seed of up to
  200 selected customers plus personas; the complete PostgreSQL batch loader remains deferred.
- PostgreSQL stays private on the data VM. This deployment does not redirect the existing public
  application's database or open a network route between the two VMs.
- Blob remains in a different region, so downloads can incur transfer charges. Both the original full
  source and derived gold remain private and outside Git.
- OS maintenance, measured batch capacity, retained state, backup restore rehearsal, and resource
  lifecycle remain operator responsibilities. No hosted language model is introduced.
