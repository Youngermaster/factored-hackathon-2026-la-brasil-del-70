import { describe, expect, it } from 'vitest';

import type { EvaluationSummary } from '@/features/eval-report';

import type { ModelCard, ModelInventory } from '../api/supervision';
import {
  cardGroups,
  isServing,
  latestComparableRun,
  lowerIsBetter,
  metricNames,
  position,
} from './evidence';

function card(overrides: Partial<ModelCard>): ModelCard {
  return {
    component: 'router',
    model: 'router:keyword@1',
    role: 'default',
    note: null,
    use: null,
    split: 'test',
    sample_size: 601,
    sample_unit: 'items',
    kind: 'provisional',
    metrics: [{ name: 'macro_f1', value: 0.385, low: 0.299, high: 0.439, unit: 'ratio' }],
    source: 'docs/models/router.md',
    report: 'docs/evaluation/router.md',
    generated_at: '2026-09-27T20:09:44Z',
    git_sha: '2c19633',
    ...overrides,
  };
}

function summary(runId: string, system: string, generatedAt: string): EvaluationSummary {
  const metrics = {
    cases: 1,
    safe_automated_resolution: { count: 1, denominator: 1 },
    containment: { count: 1, denominator: 1 },
    escalation_missed: { count: 0, denominator: 1 },
    escalation_unnecessary: { count: 0, denominator: 1 },
    unsafe_outcomes: { count: 0, denominator: 1 },
    latency_p50_ms: null,
    latency_p95_ms: null,
    cost_per_attempted_case_usd: null,
    automation_attempted: null,
    cost_per_resolution_usd: null,
  };
  return {
    schema_version: '1.1.0',
    run_id: runId,
    system,
    generated_at: generatedAt,
    git_sha: 'abc1234',
    dataset_version: 'v1',
    measurement: 'simulated',
    workflows: [{ ...metrics, workflow: 'credit' }],
    aggregate: metrics,
    breakdowns: [],
    failure_table: null,
    notes: [],
  };
}

describe('supervision evidence helpers', () => {
  it('groups cards per component and task with the default first', () => {
    const groups = cardGroups([
      card({ component: 'resolver', model: 'resolver:lgbm@1', role: 'champion', use: 'dispute' }),
      card({ model: 'router:tfidf@9', role: 'champion' }),
      card({}),
      card({ component: 'resolver', model: 'resolver:rules@1', use: 'dispute' }),
    ]);
    expect(groups.map((group) => group.key)).toEqual(['router', 'resolver:dispute']);
    expect(groups[0]?.cards.map((item) => item.model)).toEqual([
      'router:keyword@1',
      'router:tfidf@9',
    ]);
    expect(groups[1]?.cards[0]?.model).toBe('resolver:rules@1');
  });

  it('marks the card whose model the process serves', () => {
    const inventory = {
      components: [
        {
          component: 'router',
          selected: 'keyword@1',
          served: 'router:keyword@1',
          kind: 'baseline',
          alias: null,
          fell_back: false,
          reason: null,
        },
      ],
    } as unknown as ModelInventory;
    expect(isServing(card({}), inventory)).toBe(true);
    expect(isServing(card({ model: 'router:tfidf@9' }), inventory)).toBe(false);
    expect(isServing(card({}), undefined)).toBe(false);
  });

  it('knows which metrics are better when lower and lists names once', () => {
    expect(lowerIsBetter('brier')).toBe(true);
    expect(lowerIsBetter('roc_auc')).toBe(false);
    expect(metricNames([card({}), card({ model: 'router:tfidf@9', role: 'champion' })])).toEqual([
      'macro_f1',
    ]);
  });

  it('picks the newest run that has the proposed system', () => {
    const run = latestComparableRun([
      summary('old', 'proposed', '2026-09-01T00:00:00Z'),
      summary('baseline-only', 'baseline_b0', '2026-09-03T00:00:00Z'),
      summary('new', 'proposed', '2026-09-02T00:00:00Z'),
    ]);
    expect(run?.runId).toBe('new');
    expect(latestComparableRun([])).toBeUndefined();
  });

  it('clamps plot positions to the axis', () => {
    expect(position(0.5, 1)).toBe(50);
    expect(position(2, 1)).toBe(100);
    expect(position(-1, 1)).toBe(0);
    expect(position(1, 0)).toBe(0);
  });
});
