# Azure data execution status

Updated: 2026-10-04. Owner: Julian Valencia. Subscription: `32847dfa-5fd4-4276-8bdf-243d72b35119`.
Scope: dedicated compute `vm-bank-database` in `rg-bank-agent`, `westus2`; private Blob storage
in `rg-la70-test`, `eastus2`. The architecture and commands are in
[the deployment guide](../../deploy/azure-data/README.md).

## Verified evidence

| Requirement | Evidence | Status |
|---|---|---|
| Correct identity and tenant | Azure CLI reports the requested subscription, tenant, and operator | Verified |
| Infrastructure preflight | Dedicated westus2 VM ARM validation and provisioning both returned `Succeeded` | Verified in Azure |
| Subscription offer | Azure reports `FreeTrial_2014-09-01` with spending limit on; the quota request returned `ResourceNotAvailableForOffer` | Offer upgrade required before requesting more quota |
| Existing compute | The Nequi AKS node pool uses two `Standard_D2s_v6` instances, accounting for all 4 regional vCPU; no changes were made | Outside authorized scope |
| Alternative-region preflights | Tested VM placements in eastus and centralus returned `SkuNotAvailable`; no resources were created there | Tested placements unavailable |
| Private artifact storage | `stla70238253ae46a02964` is `Succeeded` in `eastus2`; `artifacts` has no public access, Shared Key is disabled, minimum TLS is 1.2 | Verified in Azure |
| Reference-value reconciliation | 10 PostgreSQL/unit tests passed, including money, currency, timestamp, and credit-score corruption | Verified locally |
| Artifact and stage safety | 17 tests passed, including archive corruption, unsafe paths and links, preserved existing state, and failure before ingestion/PostgreSQL | Verified locally |
| Full local application path | Fresh sample preparation, strict PostgreSQL reconciliation, eight es/pt workflow checks, cross-customer 404, and zero loaded objects on unchanged ingestion passed in the integration suite | Verified locally |
| Dedicated VM | `vm-bank-database` is running in westus2 with 2 vCPU, 8 GiB RAM, a verified 128 GiB disk, and denied inbound access | Verified in Azure |
| VM pipeline execution | Run `20261004T175314Z-59a43e8fea4d` restored the complete source and is ingesting; PostgreSQL reconciliation and retained-state rerun remain pending | Running in Azure |
| Full gold migration | Five private Parquet files, 5,192,103 rows, 241,693,714 bytes; each downloaded SHA-256 matches the validated local file | Verified in Azure Blob |
| Full input migration | 7,671 contracted source objects archived privately; uploaded archive downloaded and SHA-256 verified; complete per-file restoration passed locally | Verified in Azure Blob |
| Cloud code publication | Release `bb6069e6c01f106041ff239d331107a2993b6343` uploaded privately, downloaded, and SHA-256 verified | Verified in Azure |
| Repository-wide checks | `make check` passed: 2,887 unit, 1,532 integration, 349 web, 11 coverage gates, docs/data/code-generation checks, and the history secret scan; ShellCheck also passed | Verified locally |

Three optional real-embedding tests were skipped because the ml extra is absent. The full suite ran in the
current working tree; existing uncommitted card-support changes remain outside the published release.
The resource group itself is `Succeeded` in `eastus2` with the requested project, event, and environment tags.
The original eastus2 preflight returned `QuotaExceeded`. The operator subsequently authorized a
separate data VM in westus2; provisioning succeeded without changing the existing application or Nequi.

## Completion criteria

Upload the committed release, execute the full local source on the dedicated data VM, inspect the actual
systemd unit and result file, publish artifacts, and repeat the run. Record the resource inventory, revision,
run identifiers, hashes, row counts, eight workflow checks, customer-isolation result, unchanged ingestion,
and retained database state here. Report all failures explicitly. Passing local tests is not evidence of a
successful Azure run. The goal stays unfinished until the cloud run and required repository checks pass.

## Published code release

- Revision: `bb6069e6c01f106041ff239d331107a2993b6343`.
- SHA-256: `3f0d545f1bff19e033c8e8102390ea56c88e047ea8597ae5c55352455b7f6b16`.
- Private blob: `artifacts/releases/3f0d545f1bff19e033c8e8102390ea56c88e047ea8597ae5c55352455b7f6b16.tar.gz`.
- The archive contains committed code and the governed sample; uncommitted card-support changes and local
  source files are excluded. This is code-publication evidence, not a VM execution artifact.

## Compute diagnosis

The eastus2 regional limit is an Azure subscription quota, not an architecture rule. Its 4 vCPU are
already allocated to the existing Nequi AKS node pool in a different resource group. A separate 2-vCPU
VM requires 6 total regional vCPU while those nodes remain allocated. The operator prohibited changes
to other resource groups; scaling or reusing that cluster requires a new explicit instruction.

The subscription currently uses the Free Trial offer. A quota increase requires upgrading that offer
first, as documented in [Azure subscription limits](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/azure-subscription-service-limits).
Retrying the same portal quota request alone does not resolve this offer restriction. No billing
change was made. Read-only SKU discovery and ARM validation also tested D2s_v6 and B2ms in eastus, and
D2s_v3 plus D2s_v6 (including zone 2) in centralus. All tested placements returned `SkuNotAvailable`.
This does not establish that every region or VM size is unavailable.

## Full gold snapshot in private Azure Blob

The full local gold snapshot was published using Azure CLI with Entra login authentication, without
Shared Key or SAS credentials. All five Parquet files were checked against their DuckDB gold tables
using `EXCEPT ALL` in both directions before upload; every difference count was zero. An incremental
source check listed 7,671 objects: zero new, changed, loaded, quarantined, or failed objects.

The private container is `artifacts` in `stla70238253ae46a02964`. Objects use content-addressed names
under `datasets/local/organizer-v1.0.0-2026-08-31/2026-06-17/`. Uploads used `--overwrite false`;
each object was downloaded and SHA-256 checked before the manifest was published last. This migrated
gold and evidence, not raw organizer CSVs. Full data and local transfer files remain outside Git.

| Gold table | Rows | Bytes | SHA-256 |
|---|---|---|---|
| `customers_serving` | 150,000 | 5,117,349 | `bb2c7f9db3af749c66372583916d2976fa10cf0a0afbf362f7f4a7ff907c137f` |
| `products_serving` | 400,000 | 14,178,140 | `682ea0e22b7327959af2298323d5bfb0f9deee51525c9a4c707c35a22897c443` |
| `transactions_serving` | 4,425,008 | 215,416,281 | `63a97d58ba1e4081ff0d5a900d86a7477544cc787ca5e1e3d1ab9b7646015272` |
| `complaints_serving` | 67,095 | 3,086,615 | `2bb0968d0e7ffe10548ab1b33d02ea551e79d16b2d612d35ac1902a1e023c1f0` |
| `credit_profiles_serving` | 150,000 | 3,895,329 | `c6d629326660baf3ea70761aac8b1b1810e10e6a59f3e11f858ef1d14d2d09bd` |

- Private manifest: `artifacts/datasets/local/organizer-v1.0.0-2026-08-31/2026-06-17/manifests/00b4c9c8f0a0773ca63a35772c635a6d1b1f0b388d3960654d358d1ce59beb34/published.json`.
- Download-verified manifest SHA-256: `00b4c9c8f0a0773ca63a35772c635a6d1b1f0b388d3960654d358d1ce59beb34`.
- Validation revision: `ee397a94da95d21f85ccc8ace0ab723417e54a5e`; execution location: local.
- Dataset business snapshot: `2026-06-17`.
- Evidence: dbt tests, source freshness, quality report, lineage report, and incremental ingestion summary.

The quality result is 271 passing dbt tests and two existing warnings: 149,995 customer registration
branch references and 831 agent assigned-branch references do not resolve to the branch catalog.
Freshness has 11 passes and two warnings, for transactions and daily exchange rates; the bronze
loading timestamps predate this transfer. The warnings were retained, not suppressed. This static
snapshot does not imply current balances or repaired branch relationships.

The published manifest explicitly records `cloud_pipeline_executed=false` and
`postgres_loaded_in_azure=false`. VM execution, application PostgreSQL loading, and a verified cloud
rerun remain completion requirements. The uploaded gold snapshot can be retrieved independently
of VM provisioning.

## Full contracted source in private Azure Blob

The versioned `source` command packaged 7,671 contracted inputs (5,349,322,481 uncompressed bytes)
using revision `bb6069e6c01f106041ff239d331107a2993b6343`. It excluded ancillary files and generated
warehouses. The archive contains the per-file path, size, and SHA-256 manifest, dataset version,
business snapshot date, and packaging revision.

- Private blob: `artifacts/sources/43475e3fa4c060ffe93c2245e4e88f8bd8f1f96493a62dfd2cccbd4ee4cd7efd.tar.gz`.
- Compressed bytes: 1,332,722,002.
- Download-verified SHA-256: `43475e3fa4c060ffe93c2245e4e88f8bd8f1f96493a62dfd2cccbd4ee4cd7efd`.
- Complete local restoration verified every source member's byte count and SHA-256 before installing
  the input directory. No Azure VM restoration or pipeline execution is claimed.

`start local` now retrieves this archive with managed identity and restores it under the pipeline lock
before ingestion. A changed or damaged existing source is refused. Once compute is available, the
full local source can run on an empty application database; running a sample first does not authorize
automatic replacement of its database or source state. The bounded PostgreSQL load remains limited to
200 selected customers plus demo personas; the full gold snapshot is retained separately.

The updated `make check` completed with 2,887 unit tests, 1,532 integration tests, 349 web tests,
all 11 coverage gates, documentation/data/code-generation checks, and the history secret scan.
The same three optional embedding tests were skipped because the ml extra is absent. ShellCheck,
source-specific strict typing, and the 17 integrity/orchestration tests also passed. These checks
prove local behavior and migration integrity; compute execution remains blocked by the regional quota.

## Dedicated data VM

The operator authorized a separate `vm-bank-database` after the activity log identified a different
creator for `vm-bank-agent` and read-only inspection found the public application stack already running
there. The separate VM and its network resources are `Succeeded` in `rg-bank-agent`, westus2.
The disk is 128 GiB Standard SSD; the dedicated NSG denies all inbound traffic at priority 100.
The VM managed identity received Blob contributor access limited to the existing private container.
No public application configuration, Nequi resource, or existing database was changed.

The unmerged pipeline ADR was renumbered to 0039 after fetching main, whose ADR 0038 now describes
Azure continuous deployment. Main and current remote branches were checked; PR metadata was not
available through the current unauthenticated client. [ADR 0040](../adr/0040-isolated-bank-database-vm.md)
records the operator's new deployment scope and first full-source run.

## Application schema compatibility

The existing application runs merged main `8ac625afa4d8`, whose Alembic head is `0014`.
The data deployment imports that merged migration unchanged and supplies transaction-local
`app.staff_id` from the trusted session before exposing repositories, including after commit
and rollback. This preserves claim-scoped RLS and the assigned-agent conversation closure
trigger. The first cloud release has head `0013`; a subsequent committed release must upgrade
it to `0014` and pass reconciliation before schema compatibility is reported as verified.
The existing application VM and its database connection remain unchanged.
