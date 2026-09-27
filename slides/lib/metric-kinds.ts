/**
 * The labels the brief requires to be kept apart. Shared by the deck
 * (lib/metrics.ts) and the Node-side check (scripts/check-content.ts), which
 * cannot import the deck module because it loads YAML through Vite's ?raw.
 */
export const METRIC_KINDS = ['offline', 'provisional', 'projection', 'simulation', 'synthetic'] as const
export type MetricKind = (typeof METRIC_KINDS)[number]

/** How each kind is printed next to a number on screen. */
export const KIND_LABEL: Record<MetricKind, string> = {
  offline: 'offline measurement',
  provisional: 'offline, provisional labels',
  projection: 'projection from assumptions',
  simulation: 'simulation',
  synthetic: 'synthetic policy parameter',
}
