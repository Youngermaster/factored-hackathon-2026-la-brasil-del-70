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
| Artifact and stage safety | 19 tests passed, including archive corruption, unsafe paths and links, preserved existing state, and failure before ingestion/PostgreSQL | Verified locally |
| Full local application path | Fresh sample preparation, strict PostgreSQL reconciliation, eight es/pt workflow checks, cross-customer 404, and zero loaded objects on unchanged ingestion passed in the integration suite | Verified locally |
| Dedicated VM | `vm-bank-database` is running in westus2 with 2 vCPU, 8 GiB RAM, a verified 128 GiB disk, and denied inbound access | Verified in Azure |
| VM pipeline execution | Both full-source runs succeeded; retained-state rerun loaded zero objects, reconciled identical reference values, reached schema `0014`, and repeated eight es/pt checks plus customer-isolation 404 | Complete in Azure |
| Full gold migration | Five private Parquet files, 5,192,103 rows, 241,693,714 bytes; each downloaded SHA-256 matches the validated local file | Verified in Azure Blob |
| Full input migration | 7,671 source objects archived privately, download hash verified, restored in Azure, then reused unchanged | Verified in Azure |
| Cloud code publication | Schema-compatible release `74c46aba0058d0ab4a1f1ee80bfdfa73ce417dcf` uploaded privately, downloaded, and SHA-256 verified | Verified in Azure |
| Repository-wide checks | Updated `make check` passed: 2,889 unit, 1,536 integration, 349 web, 11 coverage gates, docs/data/code-generation checks, and the history secret scan; ShellCheck also passed | Verified locally |

Three optional real-embedding tests were skipped because the ml extra is absent. The full suite ran in the
current working tree; existing uncommitted card-support changes remain outside the published release.
The resource group itself is `Succeeded` in `eastus2` with the requested project, event, and environment tags.
The original eastus2 preflight returned `QuotaExceeded`. The operator subsequently authorized a
separate data VM in westus2; provisioning succeeded without changing the existing application or Nequi.

## Completion status

Complete for the authorized data scope: dedicated compute, full-source migration and transformation,
quality/lineage, bounded serving PostgreSQL, strict value reconciliation, schema `0014`, eight es/pt
application smoke checks, customer isolation, retained-state rerun, private evidence, and backups.
Both systemd executions and their actual result files were inspected. All downloaded archives and
recorded artifact hashes passed verification. Repository-wide checks passed; the final documentation
update passed its own gate. The existing public application's database remains separate. The full
PostgreSQL batch loader and a backup restore rehearsal remain outside this completed scope.

## Initial published code release

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
Retrying the same portal quota request alone does not resolve this offer restriction. No subscription-offer
upgrade was made. Read-only SKU discovery and ARM validation also tested D2s_v6 and B2ms in eastus, and
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

The earlier published gold-transfer manifest records `cloud_pipeline_executed=false` and
`postgres_loaded_in_azure=false`, accurately describing that earlier transfer. The cloud run evidence
below proves execution, PostgreSQL loading, and a verified retained-state rerun. The uploaded gold snapshot can be retrieved independently
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
  the input directory. The later cloud restoration and execution are recorded below.

`start local` now retrieves this archive with managed identity and restores it under the pipeline lock
before ingestion. A changed or damaged existing source is refused. Once compute is available, the
full local source can run on an empty application database; running a sample first does not authorize
automatic replacement of its database or source state. The bounded PostgreSQL load remains limited to
200 selected customers plus demo personas; the full gold snapshot is retained separately.

The updated `make check` completed with 2,887 unit tests, 1,532 integration tests, 349 web tests,
all 11 coverage gates, documentation/data/code-generation checks, and the history secret scan.
The same three optional embedding tests were skipped because the ml extra is absent. ShellCheck,
source-specific strict typing, and the 17 integrity/orchestration tests also passed. These earlier checks
proved local behavior and migration integrity while compute was blocked by the eastus2 quota. The
later dedicated westus2 execution and updated schema-compatible checks are recorded below.

## Dedicated data VM

The operator authorized a separate `vm-bank-database` after the activity log identified a different
creator for `vm-bank-agent` and read-only inspection found the public application stack already running
there. The separate VM and its network resources are `Succeeded` in `rg-bank-agent`, westus2.
The disk is 128 GiB Standard SSD; the dedicated NSG denies all inbound traffic at priority 100.
The VM managed identity received Blob contributor access limited to the existing private container.
The public application configuration and database, and all Nequi resources, were preserved.

The unmerged pipeline ADR was renumbered to 0039 after fetching main, whose ADR 0038 now describes
Azure continuous deployment. Main and current remote branches were checked; PR metadata was not
available through the current unauthenticated client. [ADR 0040](../adr/0040-isolated-bank-database-vm.md)
records the operator's new deployment scope and first full-source run.

## Application schema compatibility

The existing application was observed on merged main `8ac625afa4d8`, whose Alembic head is `0014`.
The data deployment imports that merged migration unchanged and supplies transaction-local
`app.staff_id` from the trusted session before exposing repositories, including after commit
and rollback. This preserves claim-scoped RLS and the assigned-agent conversation closure
trigger. The first run reached head `0013`; the retained-state run upgraded it to `0014` and
passed strict reference reconciliation. A database query verified that the new table exists with
RLS both enabled and forced. Four real-PostgreSQL compatibility tests also passed.
The existing application VM and its database connection remain unchanged.

## First complete Azure execution

- Run: `20261004T175314Z-59a43e8fea4d`; committed revision `59a43e8fea4de2132296a5c66259d682a73ed234`.
- Code archive SHA-256: `c89a28f1f511efaa3342f83f423aad9a9b7adc16a910428de96ea0622d5fe761`.
- Final status: `succeeded`; systemd unit became inactive after all recorded stages completed.
- Ingestion processed all 7,671 source objects: 23,471,159 rows loaded, 24,029 rows quarantined,
  zero failed objects. Quarantined rows are `call_transcripts` missing required `duration_seconds`;
  raw rows reconcile exactly to loaded plus quarantined rows.
- Gold counts are 150,000 customers, 400,000 products, 4,425,008 transactions, 67,095 complaints,
  and 150,000 credit profiles. All five complete file hashes match the validated local gold above.
- dbt build: 313 passes and two warnings out of 315 nodes; explicit tests: 271 passes and two
  warnings out of 273, zero errors or skips. Bronze freshness: all 13 sources pass. The two
  branch-reference warnings remain visible: 149,995 customers and 831 agents.
- Source quality also records cross-customer affected products in 44,570 complaints and 1,094,226
  digital events. Serving complaints deliberately null those foreign product references; they are
  never served as the complaining customer's product. No source values were fabricated.
- PostgreSQL head at this first run: `0013`. Strict reconciliation verified 200 customers,
  559 products, 6,119 transactions, 84 historical complaints, 200 credit profiles, 200 directory
  entries, two staff, one demo dispute, and one demo credit application. Owner and application
  roles are neither superusers nor RLS bypass roles. PostgreSQL binds only to `127.0.0.1:5432`.
- All four production ASGI workflow checks in Spanish and Portuguese passed; account and credit
  resolved, card support and dispute clarified. Cross-customer access returned 404. These checks
  use the configured fake provider and do not claim a live-model evaluation.
- Private run artifact: `artifacts/runs/5326b3db9dd1897ba72e349d369af761e051e6511fcaaf7d08c811044c67316e.tar.gz`.
  The entire archive was downloaded and hash-verified, then every recorded artifact hash was
  checked, including the custom-format PostgreSQL backup. No restore rehearsal is claimed.
- Private inspection: `artifacts/runs/20261004T175314Z-59a43e8fea4d/inspection-e00fc0a628604dfbe5d410e75e32289af877536ff70eb4bbbe3dcb535cdb6e35.json`;
  its downloaded hash matches. It preserves explicit dbt test summaries because dbt docs generation
  replaces the working `run_results.json` with catalog-generation results.

The schema-compatible release is `74c46aba0058d0ab4a1f1ee80bfdfa73ce417dcf`, download-verified
code SHA-256 `74cdb6d82c873c8c39802ed666e78d7bd2af0c96d6e8e0261e8884a7a45d3d0c`.
The retained-state run met all of those requirements, as recorded below.

## Verified retained-state rerun and closure

- Run: `20261004T191022Z-74c46aba0058`; revision `74c46aba0058d0ab4a1f1ee80bfdfa73ce417dcf`.
- Final status: `succeeded`, with the systemd unit inactive after completion.
- Source: 7,671 unchanged objects, zero new, changed, loaded, or failed objects and zero newly
  quarantined rows. The previous 24,029 quarantine rows remain in the warehouse and quality report.
- All five gold counts and file hashes match the first cloud run and validated local gold.
- PostgreSQL was retained; automatic reseeding was refused. Migration advanced `0013` to `0014`;
  strict reconciliation passed with exactly the same selected reference counts and values.
- The human messages table exists with RLS enabled and forced; owner and application remain
  non-superuser, non-bypass roles. Port 5432 remains bound to loopback.
- dbt tests again report 271 passes, two warnings, zero errors or skips; all 13 freshness checks
  pass. All eight es/pt flow checks and customer-isolation 404 pass with the fake provider.
- Private archive: `artifacts/runs/eb3d935aa6ab76676edb8ff61d4bc5cfe06f96da9bfe44c8412966c88a081c36.tar.gz`.
  Download SHA-256 and all 23 recorded artifact hashes passed, including the PostgreSQL backup.
- Private inspection: `artifacts/runs/20261004T191022Z-74c46aba0058/inspection-8bdd61fe4f2326d2dbd0312079cf2c30b9a02807949c1f010d17955db96525d4.json`;
  its downloaded hash matches.
- Final manifest: `artifacts/runs/completion/64c1d9f2fc902bfc8a59d9af0258ae32a2093f1c1b164befd282e816d8de25bd.json`;
  uploaded and downloaded SHA-256 match. It records both runs, private resource scope, source/code/run
  hashes, quality results, PostgreSQL counts, application checks, local gates, and explicit limits.

The final VM check reports `VM running` and `Succeeded` in westus2. No repository push, public
application reconfiguration, Nequi change, or quota increase was performed. The existing application
was not redirected to this private database. A final optional read-only container recheck was refused
because another Run Command was active on the existing VM; it was left alone. Schema alignment here
is tied to the previously inspected application revision, not to any concurrent deployment by another
operator.
