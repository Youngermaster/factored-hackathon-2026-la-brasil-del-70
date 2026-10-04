# Administrative analytics dashboard

The administrative dashboard is available at `/console/dashboard` to the existing `evaluator` role. The product
does not define an `admin` role. Reusing the evaluator authorization boundary avoids adding a broader privileged
identity solely for presentation. Agents and customers cannot open the page or call its data source unless the
evaluation summaries were deliberately configured as public.

The page reads `GET /v1/eval/summaries` through the existing `useSummaries` TanStack Query hook. It does not copy
evaluation files into the web build and does not calculate metrics from customer records in the browser. Each
published summary is validated by the backend's `EvaluationSummary` model before it reaches the page.

## Data reviewed

The current published test run is `test-local`, generated from commit `6bc2e9d` on 332 scenarios. Its main workload
contains 304 in-scope cases across the four workflows, plus 28 routing scenarios. The proposed system reports, on
the 304-case aggregate, 177 safe automated resolutions (58 percent), 220 contained cases (72 percent), 8 unsafe
outcomes (2.6 percent), and p95 turn latency of 10,383 ms. These are simulated, offline measurements against a
synthetic evaluation world. They are not production traffic or service-level measurements.

The workflow split explains more than the aggregate alone:

| Workflow | Safe automated resolution | Containment | Unsafe outcomes | p95 latency |
|---|---:|---:|---:|---:|
| Account inquiry | 54/76 (71%) | 62/76 (82%) | 2/76 | 9,451 ms |
| Card support | 40/76 (53%) | 51/76 (67%) | 0/76 | 6,996 ms |
| Dispute | 34/76 (45%) | 50/76 (66%) | 4/76 | 13,935 ms |
| Credit | 49/76 (64%) | 57/76 (75%) | 2/76 | 8,935 ms |

The dashboard therefore makes dispute quality and latency visible instead of letting the aggregate hide them. It
also shows language, dialect, and customer-segment slices. Those slices are diagnostic, not causal, and small
samples remain subject to the confidence-interval and review guidance in the full evaluation view.

## Controls and fields

| Field | Source | Calculation and meaning |
|---|---|---|
| Measurement badge | `measurement` | `offline`, `simulated`, or `projected`; always visible so a projection cannot look like a measurement |
| Run | `run_id`, grouped with `dataset_version` | Selects one comparable run and dataset; changing it resets the system selection |
| System analyzed | `system` | Selects H, B0, B1, P, or another published system; P is selected first when present |
| Cases | `aggregate.cases` | Number of in-scope cases in the selected summary |
| Safe automated resolution | `aggregate.safe_automated_resolution` | `count / denominator`; a correct, policy-compliant outcome without human intervention |
| Difference from baseline | selected and B0 safe-resolution rates | Selected rate minus B0 rate, in percentage points; if B0 is absent, the first other system is used and named |
| Unsafe outcomes | `aggregate.unsafe_outcomes` | Count over denominator, with the derived rate in supporting text; counts lead because zero and rare events matter |
| Containment | `aggregate.containment` | Cases ending without transfer divided by its denominator; it is never presented as success by itself |
| Automation attempted | `aggregate.automation_attempted` | Cases where automation was attempted divided by all in-scope cases |
| Latency p95 | `aggregate.latency_p95_ms` | 95th percentile of measured per-turn latency in milliseconds |
| Latency p50 | `aggregate.latency_p50_ms` | Median measured per-turn latency, shown beneath p95 |
| Cost per resolution | `aggregate.cost_per_resolution_usd` | Published model cost divided by safe automated resolutions; `No definido` when the run did not publish it |
| Cost per attempted case | `aggregate.cost_per_attempted_case_usd` | Published model cost divided by cases where automation was attempted |

## Visualizations and analytical sections

### Performance by workflow

Each horizontal bar is the selected system's safe automated-resolution rate for one of the four workflows. The
text below each bar adds containment, unsafe-outcome count over denominator, and the percentage-point difference
from the named baseline. The chart uses semantic HTML and an accessible label; color is not the only carrier of
meaning.

### Safety and escalation

| Field | Source | Interpretation |
|---|---|---|
| Missed transfers | `escalation_missed` | Required transfers that did not happen, over cases that required transfer |
| Unnecessary transfers | `escalation_unnecessary` | Transfers that were not required, over cases that did not require transfer |
| Unsafe outcomes | `unsafe_outcomes` | Unauthorized disclosure or action, or a materially incorrect outcome, over evaluated cases |

These metrics keep their distinct denominators. The page never adds them together.

### Overall system comparison

One row per system compares safe automated resolution, unsafe outcomes, containment, and p95 latency on the same
run and dataset. This prevents comparisons between incompatible workloads. The complete evaluation tables remain
available at `/console/evaluation` for confidence intervals and small-cell warnings.

### Population consistency

The language, dialect, and segment panels use only aggregate slices where `workflow` is null. Each item shows the
safe automated-resolution rate and count over denominator. Missing panels say `No definido`; the UI never treats a
missing slice as zero.

### Provenance

The final panel shows the measurement label, dataset version, generation time, abbreviated Git SHA, and failure
table path. It explicitly states that offline or simulated results are not production outcomes.

## States, accessibility, and localization

- Loading uses content-shaped skeletons; failures include the request id and a retry action; an empty state explains
  that an evaluation run must be published.
- Native selects provide keyboard navigation and platform accessibility. Tables remain keyboard-scrollable.
- The page is responsive from one column to the dense desktop console layout and supports light and dark themes.
- All copy exists in Spanish, Brazilian Portuguese, and English. Numbers, money, and times use the shared locale
  formatters.
- The feature has integration coverage for data selection, baseline deltas, workflow and population sections,
  provenance, role protection, and automated accessibility checks.

## Files

| Path | Responsibility |
|---|---|
| `apps/web/src/features/admin-dashboard/model/dashboard.ts` | Pure rate, baseline, system, and workflow selection helpers |
| `apps/web/src/features/admin-dashboard/ui/AdminDashboard.tsx` | Query states, controls, KPIs, charts, comparison table, slices, and provenance |
| `apps/web/src/features/admin-dashboard/ui/MetricCard.tsx` | Compact semantic KPI card |
| `apps/web/src/pages/dashboard/AdminDashboardPage.tsx` | Evaluator-only route composition |
| `apps/web/src/features/admin-dashboard/admin-dashboard.test.tsx` | Integration, interaction, and accessibility coverage |
