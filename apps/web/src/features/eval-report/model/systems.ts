import type { EvaluationSummary } from '../api/summaries';

/** The brief's systems in reading order: the human baseline, the two baselines, then the proposed system. */
const ORDER = ['h', 'b0', 'b1', 'p'] as const;
export type SystemCode = (typeof ORDER)[number];

const ALIASES: Record<string, SystemCode> = {
  h: 'h',
  human: 'h',
  b0: 'b0',
  baseline_b0: 'b0',
  b1: 'b1',
  baseline_b1: 'b1',
  p: 'p',
  proposed: 'p',
};

/** The short label for a published system id (H, B0, B1, P), or null for an id the brief does not name. */
export function systemCode(system: string): SystemCode | null {
  return ALIASES[system] ?? null;
}

function rank(system: string): number {
  const code = systemCode(system);
  return code === null ? ORDER.length : ORDER.indexOf(code);
}

export interface RunGroup {
  readonly runId: string;
  readonly datasetVersion: string;
  readonly generatedAt: string;
  readonly summaries: readonly EvaluationSummary[];
}

/**
 * Summaries grouped by run and dataset, newest first, each group's systems in the brief's order. Baseline and
 * proposed numbers are compared only within one run on one workload.
 */
export function groupRuns(summaries: readonly EvaluationSummary[]): RunGroup[] {
  const groups = new Map<string, EvaluationSummary[]>();
  for (const summary of summaries) {
    const key = `${summary.run_id}|${summary.dataset_version}`;
    groups.set(key, [...(groups.get(key) ?? []), summary]);
  }
  return [...groups.values()]
    .map((items) => {
      const sorted = [...items].sort(
        (a, b) => rank(a.system) - rank(b.system) || a.system.localeCompare(b.system),
      );
      const first = sorted[0];
      if (first === undefined) {
        throw new Error('a run group always holds at least one summary');
      }
      const newest = sorted.reduce(
        (at, item) => (item.generated_at > at ? item.generated_at : at),
        first.generated_at,
      );
      return {
        runId: first.run_id,
        datasetVersion: first.dataset_version,
        generatedAt: newest,
        summaries: sorted,
      };
    })
    .sort((a, b) => b.generatedAt.localeCompare(a.generatedAt));
}
