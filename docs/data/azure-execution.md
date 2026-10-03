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
| VM pipeline execution | No VM exists yet; no cloud pipeline run or application result is claimed | Pending |
| Cloud artifact publication | Storage is ready; committed release publication remains to be verified | Pending |
| Repository-wide checks | Lint, typing, 2,876 unit tests, ShellCheck, and documentation checks passed; integration suite is running | In progress |

## Completion criteria

After quota is approved: provision, upload the committed release, execute the sample, inspect the actual
systemd unit and result file, publish artifacts, and repeat the run. Record the resource inventory, revision,
run identifiers, hashes, row counts, eight workflow checks, customer-isolation result, unchanged ingestion,
and retained database state here. Report all failures explicitly. Passing local tests is not evidence of a
successful Azure run. The goal stays unfinished until the cloud run and required repository checks pass.
