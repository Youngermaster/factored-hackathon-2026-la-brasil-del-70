import { groupRuns, systemCode, type EvaluationSummary } from '@/features/eval-report';

import type { CardMetric, ModelCard, ModelInventory, ServedModel } from '../api/supervision';

export type Component = ModelCard['component'];

/** The four workflows in the brief's order; tables list them before the aggregate. */
export const WORKFLOWS = ['account_inquiry', 'card_support', 'dispute', 'credit'] as const;

/** Metrics where a lower value is better; every other published metric is better when higher. */
const LOWER_IS_BETTER: ReadonlySet<string> = new Set([
  'error_among_covered',
  'ece',
  'brier',
  'wrong_transaction_rate',
  'wrong_among_auto',
  'false_abstention',
  'latency_p95_ms',
]);

export function lowerIsBetter(metric: string): boolean {
  return LOWER_IS_BETTER.has(metric);
}

/** The metric each component is compared on in the plot; the table next to it shows every metric. */
export const HEADLINE: Readonly<Record<Component, string>> = {
  router: 'macro_f1',
  resolver: 'coverage',
  risk_estimator: 'roc_auc',
  retriever: 'recall_at_1',
  language_detector: 'accuracy',
  llm: 'accuracy',
};

/** The reading order of the evidence: the learned components first, the way a request meets them. */
export const COMPONENT_ORDER: readonly Component[] = [
  'router',
  'resolver',
  'risk_estimator',
  'retriever',
];

export interface CardGroup {
  /** `router`, or `resolver:dispute` when a component is evaluated per task. */
  readonly key: string;
  readonly component: Component;
  readonly use: string | null;
  readonly cards: readonly ModelCard[];
}

/** Cards grouped by component and task, in reading order, each group's default (baseline) first. */
export function cardGroups(cards: readonly ModelCard[]): CardGroup[] {
  const groups = new Map<string, CardGroup>();
  for (const component of COMPONENT_ORDER) {
    for (const card of cards.filter((item) => item.component === component)) {
      const key = card.use === null ? component : `${component}:${card.use}`;
      const group = groups.get(key) ?? { key, component, use: card.use, cards: [] };
      groups.set(key, { ...group, cards: [...group.cards, card] });
    }
  }
  const rank = (card: ModelCard) =>
    ['default', 'champion', 'candidate', 'reference'].indexOf(card.role);
  return [...groups.values()].map((group) => ({
    ...group,
    cards: [...group.cards].sort((a, b) => rank(a) - rank(b)),
  }));
}

export function metricOf(card: ModelCard, name: string): CardMetric | undefined {
  return card.metrics.find((metric) => metric.name === name);
}

/** The metric names a group's cards publish, in first-seen order. */
export function metricNames(cards: readonly ModelCard[]): string[] {
  return [...new Set(cards.flatMap((card) => card.metrics.map((metric) => metric.name)))];
}

/** The served component for a card's component, if the process serves one. */
export function servedFor(
  inventory: ModelInventory | undefined,
  component: Component,
): ServedModel | undefined {
  return inventory?.components.find((item) => item.component === component);
}

/** True when the process currently serves exactly this card's model. */
export function isServing(card: ModelCard, inventory: ModelInventory | undefined): boolean {
  return servedFor(inventory, card.component)?.served === card.model;
}

/** The newest published run that includes the proposed system, so P can be read against its baselines. */
export function latestComparableRun(summaries: readonly EvaluationSummary[]) {
  return groupRuns(summaries).find((group) =>
    group.summaries.some((summary) => systemCode(summary.system) === 'p'),
  );
}

/** The summary of one system (B0, B1, or P) within a run, if the run published it. */
export function systemSummary(
  summaries: readonly EvaluationSummary[],
  code: 'b0' | 'b1' | 'p',
): EvaluationSummary | undefined {
  return summaries.find((summary) => systemCode(summary.system) === code);
}

/** A plot position in percent of the axis, clamped to it. */
export function position(value: number, max: number): number {
  if (max <= 0) return 0;
  return Math.min(100, Math.max(0, (value / max) * 100));
}
