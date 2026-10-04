import type { EvaluationSummary, OutcomeMetrics } from '@/features/eval-report';

export const WORKFLOWS = ['account_inquiry', 'card_support', 'dispute', 'credit'] as const;
export const DIMENSIONS = ['language', 'dialect', 'segment'] as const;

export function rate(metric: {
  readonly count: number;
  readonly denominator: number;
}): number | null {
  return metric.denominator === 0 ? null : metric.count / metric.denominator;
}

export function percentagePointDelta(
  current: { readonly count: number; readonly denominator: number },
  baseline: { readonly count: number; readonly denominator: number } | undefined,
): number | null {
  const currentRate = rate(current);
  const baselineRate = baseline === undefined ? null : rate(baseline);
  return currentRate === null || baselineRate === null ? null : (currentRate - baselineRate) * 100;
}

export function proposedOrFirst(
  summaries: readonly EvaluationSummary[],
): EvaluationSummary | undefined {
  return summaries.find((summary) => ['p', 'proposed'].includes(summary.system)) ?? summaries[0];
}

export function baselineOf(
  summaries: readonly EvaluationSummary[],
  selected: EvaluationSummary,
): EvaluationSummary | undefined {
  return (
    summaries.find(
      (summary) =>
        summary.system !== selected.system && ['b0', 'baseline_b0'].includes(summary.system),
    ) ?? summaries.find((summary) => summary.system !== selected.system)
  );
}

export function workflowMetrics(
  summary: EvaluationSummary,
  workflow: (typeof WORKFLOWS)[number],
): OutcomeMetrics | undefined {
  return summary.workflows.find((item) => item.workflow === workflow);
}
