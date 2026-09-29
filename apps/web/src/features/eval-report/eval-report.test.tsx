import { screen, within } from '@testing-library/react';
import { HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import type { Schema } from '@/shared/api';
import { renderApp } from '@/test/app';
import { axe } from '@/test/axe';
import { apiGet, sessionView } from '@/test/msw/api';
import { startAuthServer } from '@/test/msw/auth';
import { server } from '@/test/msw/server';

import { proportion, wilson, zeroEventUpperBound } from './model/stats';

type Metrics = Schema<'OutcomeMetrics'>;

const count = (n: number, d: number) => ({ count: n, denominator: d });

function metrics(cases: number, overrides: Partial<Metrics> = {}): Metrics {
  return {
    cases,
    safe_automated_resolution: count(Math.round(cases * 0.6), cases),
    automation_attempted: count(Math.round(cases * 0.8), cases),
    containment: count(Math.round(cases * 0.7), cases),
    escalation_missed: count(0, cases),
    escalation_unnecessary: count(1, cases),
    unsafe_outcomes: count(0, cases),
    latency_p50_ms: 120,
    latency_p95_ms: 480,
    cost_per_attempted_case_usd: '0.0021',
    cost_per_resolution_usd: null,
    ...overrides,
  };
}

function summary(
  system: string,
  measurement: Schema<'EvaluationSummary'>['measurement'] = 'offline',
): Schema<'EvaluationSummary'> {
  const workflows = (['account_inquiry', 'card_support', 'dispute', 'credit'] as const).map(
    (workflow, index) => ({
      ...metrics(index === 3 ? 12 : 60),
      workflow,
    }),
  );
  return {
    schema_version: '1.1.0',
    run_id: 'run-fixture-1',
    system,
    generated_at: '2026-09-29T12:00:00Z',
    git_sha: 'abc1234def',
    dataset_version: 'heldout-v1',
    measurement,
    workflows,
    aggregate: metrics(192),
    breakdowns: [
      { ...metrics(40), dimension: 'language', value: 'es', workflow: null },
      { ...metrics(20), dimension: 'language', value: 'pt', workflow: null },
    ],
    failure_table: 'docs/evaluation/failures.md',
    notes: ['Fixture summary for tests.'],
  };
}

function serve(summaries: Schema<'EvaluationSummary'>[]) {
  startAuthServer({ session: sessionView({ role: 'evaluator' }) });
  server.use(apiGet('/v1/eval/summaries', () => HttpResponse.json({ summaries })));
  renderApp({ path: '/console/evaluation' });
}

describe('evaluation statistics', () => {
  it('computes the Wilson interval and the zero-event upper bound', () => {
    const { low, high } = wilson(30, 50);
    expect(low).toBeCloseTo(0.4618, 3);
    expect(high).toBeCloseTo(0.7239, 3);
    expect(zeroEventUpperBound(40)).toBeCloseTo(0.0722, 3);
    expect(proportion(count(0, 0))).toBeNull();
    expect(proportion(count(0, 40))).toMatchObject({ zeroEvents: true, low: 0, small: false });
    expect(proportion(count(3, 12))?.small).toBe(true);
  });
});

describe('the evaluation view', () => {
  it('explains how to publish when nothing is published', async () => {
    serve([]);
    expect(await screen.findByText('Todavía no hay resultados publicados')).toBeInTheDocument();
    expect(screen.getByText('make eval')).toBeInTheDocument();
    expect(screen.getByText('EVAL_SUMMARIES_DIR')).toBeInTheDocument();
  });

  it('shows one table per workflow and then the aggregate, systems side by side with their labels', async () => {
    serve([
      summary('proposed'),
      summary('baseline_b0'),
      summary('human', 'simulated'),
      summary('baseline_b1', 'projected'),
    ]);
    const tables = await screen.findAllByRole('table');
    expect(tables.map((table) => table.querySelector('caption')?.textContent)).toEqual([
      'Cuentas y pagos: resultados por sistema',
      'Tarjetas: resultados por sistema',
      'Aclaraciones: resultados por sistema',
      'Crédito: resultados por sistema',
      'Total de los cuatro flujos: resultados por sistema',
      'Por idioma: resolución automática segura',
    ]);
    expect(await axe(document.body, { rules: { region: { enabled: true } } })).toHaveNoViolations();
    const [first] = tables;
    if (first === undefined) {
      throw new Error('the report has tables');
    }
    const headers = within(first)
      .getAllByRole('columnheader')
      .map((cell) => cell.textContent);
    expect(headers.slice(1)).toEqual([
      'H: atención humanahumanSimulado',
      'B0: menú con reglasbaseline_b0Offline',
      'B1: agente ingenuobaseline_b1Proyectado',
      'P: propuestoproposedOffline',
    ]);
  });

  it('gives every figure its sample size and interval, flags small cells, and says not defined', async () => {
    serve([summary('proposed')]);
    const credit = await screen.findByRole('table', { name: 'Crédito: resultados por sistema' });
    const safe = within(credit).getByRole('row', { name: /Resolución automática segura/ });
    expect(safe).toHaveTextContent('58.3 %');
    expect(safe).toHaveTextContent(/7 de 12, IC 95 %: 3[0-9.]+ % a 8[0-9.]+ %/);
    expect(safe).toHaveTextContent('Muestra pequeña');
    const unsafe = within(credit).getByRole('row', { name: /Resultados inseguros/ });
    expect(unsafe).toHaveTextContent(/0 de 12/);
    expect(unsafe).toHaveTextContent(/cero eventos, límite superior 95 %: 22\.1 %/);
    expect(within(credit).getByRole('row', { name: /Costo por resolución/ })).toHaveTextContent(
      'No definido',
    );
    expect(within(credit).getByRole('row', { name: /Traspasos completos/ })).toHaveTextContent(
      'No definido',
    );
    expect(screen.getByText('docs/evaluation/failures.md')).toBeInTheDocument();
  });
});
