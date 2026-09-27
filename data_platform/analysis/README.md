# Analysis inputs

The committed inputs of `bank-data analysis` (`make analysis`, phase 04). The code lives in the package, in `data_platform/src/bank_data/analysis/`, so it is typed, linted, tested, and covered like the rest of `bank-data`; the reports it writes are indexed in [`docs/analysis/README.md`](../../docs/analysis/README.md).

| File | Content | Rules |
|---|---|---|
| [`scoring.yaml`](scoring.yaml) | The pre-registered scoring: weights, sensitivity delta, tie margin, sub-intent threshold, statistics settings, labeling settings, demand-pattern settings, harm and demo-depth rubrics, data support items per workflow, and the sub-intents with capability, harm, and items | Committed before any result was computed. A change after results are seen is a new `version`, recorded with its reason in [`docs/analysis/workflow-scoring-preregistration.md`](../../docs/analysis/workflow-scoring-preregistration.md); both results are kept |
| [`cost_assumptions.yaml`](cost_assumptions.yaml) | Loaded cost per handled agent minute per country (MX, CO, AR), the after-call-work factor, and the sensitivity multipliers | Every value carries `assumption: true`, `verified: false`, and its derivation; the loader refuses a value not marked as an assumption. Costs never enter the score |
| [`../mappings/workflow_mapping.csv`](../mappings/workflow_mapping.csv) | Every observed `contact_reason`, `reason_category`, and complaint `category`/`subcategory` pair mapped to a `WorkflowId` or `other`, with the phase 02b `Intent` where one applies, the strict and alternative scenario workflows, and the rationale | A test fails when an observed value has no row, or a workflow or intent value is invalid |

## Code map

| Module | Responsibility |
|---|---|
| `config.py` | Loads and validates the three inputs |
| `queries.py` | Read-only warehouse queries and the data support item definitions |
| `metrics.py` | First contact resolution, escalation, SLA breach, the proxy, and costs |
| `stats.py` | Seeded bootstrap intervals, Cohen's kappa, Cramer's V, robust spike detection |
| `scoring.py` | Normalization, weighted scores, tie-aware ordering, weight sensitivity, sub-intent classes |
| `evidence.py` | Every section of the evidence, as one JSON-serializable result |
| `labeling.py` | The stratified labeling sample, machine pre-labels, and reading human labels |
| `figures.py`, `render.py` | The PNG figures and the two Markdown reports |
| `runner.py` | Orchestration and output paths (`docs/analysis/` only for the organizer source) |

## How to extend

- **Add a criterion or change a weight:** edit `scoring.yaml` as a new version, update the pre-registration document in the same commit, and add the criterion to `config.CRITERIA` and `evidence._criteria`.
- **Add a data support item:** add a `DataSupportItem` with its SQL to `queries.DATA_SUPPORT_ITEMS`, list it under a workflow or sub-intent in `scoring.yaml` (new version), and document it in the pre-registration table.
- **Map a new reason:** add a row to the mapping CSV with a rationale and all three scenario columns; the coverage test checks it.
- **Add a figure:** add the name to `figures.FIGURE_NAMES`, draw it in `write_figures`, and link it from `render.py`; the integration test checks that every expected file is written.

## How to test

```bash
uv run pytest data_platform/tests/unit -k "analysis or mapping" -q      # metrics, statistics, scoring, config, labeling, mapping coverage
uv run pytest data_platform/tests/integration/test_analysis.py -q      # the whole analysis on the phase 03 fixture
```
