# 0036: Provisioned Grafana for live analytics, separate from offline evaluation

- Status: accepted
- Date: 2026-10-03

## Context

The administrative experience needs both a concise view of product and service behavior and evidence from the
frozen evaluation harness. The two sources answer different questions. OpenTelemetry metrics describe traffic in a
running environment and are retained by Prometheus for a bounded period. Evaluation summaries describe versioned
systems on labeled, synthetic scenarios and include metrics such as safe automated resolution, containment, and
population slices that cannot be inferred from live outcome counters.

The repository already provisions OpenTelemetry Collector, Prometheus, Grafana, and a detailed reliability
dashboard. It also has an evaluator-only React dashboard over `GET /v1/eval/summaries`. Treating a live `resolved`
turn as an offline safe automated resolution would erase the policy and grading checks that make the evaluation
metric meaningful.

## Considered options

1. Keep every administrative metric in the React application. This preserves the existing application session and
   localization model, but requires a new time-series API, aggregation logic, charting behavior, and operational
   query surface that duplicate Grafana and Prometheus.
2. Put live telemetry and frozen evaluation results into one Grafana dashboard. This gives operators one tool, but
   requires exporting evaluation artifacts as time-series metrics or adding another datasource. Either approach
   weakens provenance and makes offline benchmark results easy to mistake for production behavior.
3. **Use provisioned Grafana dashboards for live analytics and retain the evaluator-only React dashboard for
   offline evaluation evidence.** Link the two through documentation and explicit measurement labels rather than
   merging their data models.

## Decision

- Provision `bank-agent-executive` in the existing **Bank agent** Grafana folder, alongside
  `bank-agent-overview`. The executive dashboard uses only the existing Prometheus datasource and privacy-safe
  instrument catalog.
- Show live turn volume, resolved and escalated outcome shares, latency, active sessions, language and workflow mix,
  handoff reasons, safety interventions, blocked unsafe responses, tool status and latency, model fallbacks, known
  model cost, HTTP status and latency, rate-limit rejections, and degradation level. Filters are the Grafana time
  range, workflow, and language where the underlying instrument carries that label.
- Keep `/console/dashboard` as the evaluator-authorized view of published offline, simulated, or projected
  summaries. It remains the source for safe automated resolution, containment, system comparisons, confidence
  guidance, population slices, and run provenance.
- Keep the dashboards as read-only JSON provisioning in Git. A repository check parses every provisioned dashboard
  and rejects PromQL that references a project metric outside the telemetry catalog.
- Do not embed Grafana into the public customer application. Development binds it to loopback with anonymous viewer
  access. Production binds it to loopback, disables anonymous access, requires the Grafana login, and is reached
  through the documented SSH tunnel.
- Do not add customer identifiers, conversation text, banking amounts, credit profiles, or risk estimates to metric
  labels. Investigation of one conversation continues through its execution record and trace ID.

## Consequences

- Administrators get a browser-based live dashboard without adding an operational analytics API or charting
  dependency to the product frontend.
- Evaluation evidence keeps its version, dataset, measurement label, and denominator semantics instead of being
  flattened into operational counters.
- There are two administrative surfaces to explain and operate. The Grafana guide names the purpose and field
  formula of each, and the web console cannot serve as a transparent proxy when Grafana is loopback-only.
- Grafana history is bounded by Prometheus retention and is not an audit ledger. Period totals can be approximate at
  range boundaries because Prometheus extrapolates counter increases.
- `resolved` is explicitly labeled as an operational outcome, not proof of a safe automated resolution. Reviewers
  must use the evaluation summary for claims about quality or policy compliance.
- Dashboard changes require updating provisioned JSON and passing catalog, PromQL, documentation, and live
  provisioning checks. Durable changes cannot be made only through the Grafana UI.
