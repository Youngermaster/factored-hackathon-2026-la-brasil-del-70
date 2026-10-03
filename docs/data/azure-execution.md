# Azure data execution status

Date: 2026-10-03. Owner: Julian Valencia. Subscription: `32847dfa-5fd4-4276-8bdf-243d72b35119`.
Scope: `rg-la70-test`, `eastus2`. The architecture and commands are in
[the deployment guide](../../deploy/azure-data/README.md).

## Verified evidence

| Requirement | Evidence | Status |
|---|---|---|
| Correct identity and tenant | Azure CLI reports the requested subscription, tenant, and operator | Verified |
| Infrastructure preflight | ARM validation reached Compute and returned `QuotaExceeded`: 4 used of 4, 2 more required | Waiting for quota |
| Automatic quota request | `az quota update` for regional cores to 6 returned `ResourceNotAvailableForOffer`; human will request through the portal | Waiting for Azure |
| Private artifact storage | `stla70238253ae46a02964` is `Succeeded` in `eastus2`; `artifacts` has no public access, Shared Key is disabled, minimum TLS is 1.2 | Verified in Azure |
| Reference-value reconciliation | 10 PostgreSQL/unit tests passed, including money, currency, timestamp, and credit-score corruption | Verified locally |
| Artifact and stage safety | 6 tests passed, including hash mismatch preservation and failure before PostgreSQL | Verified locally |
| Full local application path | Fresh sample preparation, strict PostgreSQL reconciliation, eight es/pt workflow checks, cross-customer 404, and zero loaded objects on unchanged ingestion passed in the integration suite | Verified locally |
| VM pipeline execution | No VM exists yet; no cloud pipeline run or application result is claimed | Pending |
| Cloud code publication | Release `0ccfa6ded3f2585bdf440a95c893d3d48a85264b` uploaded privately, downloaded, and SHA-256 verified | Verified in Azure |
| Repository-wide checks | `make check` passed: 2,876 unit, 1,532 integration, 349 web, 11 coverage gates, docs/data/code-generation checks, and the history secret scan; ShellCheck also passed | Verified locally |

Three optional real-embedding tests were skipped because the ml extra is absent. The full suite ran in the
current working tree; existing uncommitted card-support changes remain outside the published release.
The resource group itself is `Succeeded` in `eastus2` with the requested project, event, and environment tags.
The final Compute preflight still returned `QuotaExceeded` (4 used of 4, minimum limit 6).

## Completion criteria

After quota is approved: provision, upload the committed release, execute the sample, inspect the actual
systemd unit and result file, publish artifacts, and repeat the run. Record the resource inventory, revision,
run identifiers, hashes, row counts, eight workflow checks, customer-isolation result, unchanged ingestion,
and retained database state here. Report all failures explicitly. Passing local tests is not evidence of a
successful Azure run. The goal stays unfinished until the cloud run and required repository checks pass.

## Published code release

- Revision: `0ccfa6ded3f2585bdf440a95c893d3d48a85264b`.
- SHA-256: `4c8234c6e930803bd818bf2411ce72c398a0f70f86b8ca7ad29c88ccd09879b6`.
- Private blob: `artifacts/releases/4c8234c6e930803bd818bf2411ce72c398a0f70f86b8ca7ad29c88ccd09879b6.tar.gz`.
- The archive contains committed code and the governed sample; uncommitted card-support changes and local
  source files are excluded. This is code-publication evidence, not a VM execution artifact.
