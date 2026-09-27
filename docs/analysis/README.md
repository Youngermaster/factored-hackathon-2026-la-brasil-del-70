# Analysis

Demand evidence and workflow prioritization for the four in-scope workflows (phase 04). The decision that uses this evidence is [`docs/decisions/workflow-prioritization.md`](../decisions/workflow-prioritization.md).

## Dataset version

Every generated report here comes from the **full organizer delivery** (`BANK_DATA_SOURCE=s3`): delivery `organizer-v1.0.0-2026-08-31`, contacts from 2023-06-17 to 2026-06-17 (686,296 interactions, 67,095 complaints, 212,759 surveys, 15,620,994 digital events), built by `make pipeline DATA_SOURCE=s3` in phase 03. Each generated file carries its generation timestamp, git commit, source, delivery, and pre-registration version in its header. Runs on the committed sample or a fixture write next to their own warehouse and never overwrite these files.

## Reports

| File | Kind | Content |
|---|---|---|
| [workflow-scoring-preregistration.md](workflow-scoring-preregistration.md) | Written, committed before results | Criteria, weights, formulas, columns, rubrics, data support items, mapping scenarios, sensitivity, and the prioritization and sub-intent rules |
| [workflow-evidence.md](workflow-evidence.md) | Generated | Per workflow: volume and trend, first contact resolution, escalation, handle and wait time, CSAT, NPS, CES, complaint SLA and outcomes, channel and country mix, demand patterns and spikes, the digital-error lag, the cost baseline, the segment baseline, data support, the transcript signal check, and the stop conditions |
| [workflow-scores.md](workflow-scores.md) | Generated | Criterion values, weighted scores, ranking, weight sensitivity, mapping sensitivity, and sub-intent scores and classes |
| [analysis-results.json](analysis-results.json) | Generated | Every number behind the two reports, for later phases (baselines for phase 14) |
| [figures/](figures/) | Generated | `monthly-volume.png`, `hour-of-day.png`, `day-of-week.png`, `error-contact-lag.png`, `scores.png` |
| [labeling-protocol.md](labeling-protocol.md) | Written | The automatable-share labeling task, its definitions per workflow, and the transcript limitation |

Inputs: [`data_platform/mappings/workflow_mapping.csv`](../../data_platform/mappings/workflow_mapping.csv) (reason to workflow), [`data_platform/analysis/scoring.yaml`](../../data_platform/analysis/scoring.yaml) (pre-registered scoring), [`data_platform/analysis/cost_assumptions.yaml`](../../data_platform/analysis/cost_assumptions.yaml) (cost assumptions, all labeled `assumption: true`). The code is `data_platform/src/bank_data/analysis/`.

## Regenerating

```bash
make pipeline DATA_SOURCE=s3     # once: the full warehouse (phase 03)
make analysis DATA_SOURCE=s3     # about 30 seconds; rewrites every generated file above
```

`make analysis` also writes the labeling files under the gitignored `data/labeling/`: `automatable_sample.csv` (600 items for the labelers) and `automatable_prelabels.csv` (machine pre-labels, `review_status=pending`). It never overwrites a sample file that already holds human labels, and it reads those labels on every run.

On the same warehouse, a rerun changes only the generation timestamp and commit in the headers; the figures are written without embedded dates, so they stay byte-identical.

## Reading the numbers

- Everything is an offline measurement of historical synthetic data, except costs, which are projections from stated assumptions. Nothing here is a measured production improvement.
- The automatable share is a structured proxy until humans label (status per workflow in both reports).
- The mapping from coarse contact reasons to workflows is an assumption for three of the four workflows; read the strict and alternative scenarios in `workflow-scores.md` before relying on a middle-rank difference.
